"""Unit tests for extractor.py — ffmpeg subprocess calls."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tb.extractor import ExtractionError, extract_frame, extract_full_audio, extract_segment_audio


@patch("tb.extractor.subprocess.run")
def test_extract_full_audio_calls_correct_flags(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0)
    result = extract_full_audio(Path("/tmp/video.mp4"), Path("/tmp/out.wav"))
    assert result == Path("/tmp/out.wav")
    args = mock_run.call_args[0][0]
    assert "-vn" in args
    assert "pcm_s16le" in args
    assert "-ac" in args and "2" in args
    assert "-ar" in args and "44100" in args


@patch("tb.extractor.subprocess.run")
def test_extract_segment_audio_uses_ss_and_to(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0)
    extract_segment_audio(Path("/tmp/video.mp4"), 10.0, 20.0, Path("/tmp/seg.wav"))
    args = mock_run.call_args[0][0]
    assert "-ss" in args
    assert "-to" in args
    assert "10.0" in args
    assert "20.0" in args


@patch("tb.extractor.subprocess.run")
def test_extract_frame_ss_before_i(mock_run: MagicMock) -> None:
    """Verify -ss appears before -i for fast seeking."""
    mock_run.return_value = MagicMock(returncode=0)
    extract_frame(Path("/tmp/video.mp4"), 5.0, Path("/tmp/frame.png"))
    args = mock_run.call_args[0][0]
    assert "-ss" in args
    assert "-frames:v" in args
    assert "1" in args
    # -ss must come before -i
    assert args.index("-ss") < args.index("-i")


@patch("tb.extractor.subprocess.run")
def test_extract_full_audio_raises_extraction_error(mock_run: MagicMock) -> None:
    mock_run.side_effect = subprocess.CalledProcessError(1, "ffmpeg", stderr=b"error detail")
    with pytest.raises(ExtractionError):
        extract_full_audio(Path("/tmp/video.mp4"), Path("/tmp/out.wav"))


@patch("tb.extractor.subprocess.run")
def test_extract_segment_audio_raises_extraction_error(mock_run: MagicMock) -> None:
    mock_run.side_effect = subprocess.CalledProcessError(1, "ffmpeg", stderr=b"error detail")
    with pytest.raises(ExtractionError):
        extract_segment_audio(Path("/tmp/video.mp4"), 0.0, 10.0, Path("/tmp/seg.wav"))


@patch("tb.extractor.subprocess.run")
def test_extract_frame_raises_extraction_error(mock_run: MagicMock) -> None:
    mock_run.side_effect = subprocess.CalledProcessError(1, "ffmpeg", stderr=b"error detail")
    with pytest.raises(ExtractionError):
        extract_frame(Path("/tmp/video.mp4"), 5.0, Path("/tmp/frame.png"))


@patch("tb.extractor.subprocess.run")
def test_extraction_error_wraps_called_process_error(mock_run: MagicMock) -> None:
    original = subprocess.CalledProcessError(1, "ffmpeg", stderr=b"codec error")
    mock_run.side_effect = original
    with pytest.raises(ExtractionError) as exc_info:
        extract_full_audio(Path("/tmp/video.mp4"), Path("/tmp/out.wav"))
    assert exc_info.value.__cause__ is original
