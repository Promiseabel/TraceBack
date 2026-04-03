"""Unit tests for fingerprinter.py — pyacoustid Chromaprint fingerprinting."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import acoustid
import pytest

from traceback.fingerprinter import fingerprint_audio
from traceback.models import FingerprintResult, Segment


def _make_segment(index: int = 0, start: float = 0.0, end: float = 15.0) -> Segment:
    return Segment(index=index, start_time=start, end_time=end, duration=end - start)


@patch("traceback.fingerprinter.acoustid.fingerprint_file")
def test_fingerprint_audio_happy_path(mock_fp_file: MagicMock) -> None:
    mock_fp_file.return_value = (12.5, "AQAAUFqkMVmyJMHW")
    seg = _make_segment()
    result = fingerprint_audio(Path("/tmp/audio.wav"), seg)
    assert isinstance(result, FingerprintResult)
    assert result.duration == 12.5
    assert result.fingerprint == "AQAAUFqkMVmyJMHW"
    assert result.segment is seg


@patch("traceback.fingerprinter.acoustid.fingerprint_file")
def test_fingerprint_audio_passes_maxlength(mock_fp_file: MagicMock) -> None:
    mock_fp_file.return_value = (10.0, "AQAA")
    fingerprint_audio(Path("/tmp/audio.wav"), _make_segment())
    _, kwargs = mock_fp_file.call_args
    assert kwargs.get("maxlength") == 120


@patch("traceback.fingerprinter.acoustid.fingerprint_file")
def test_fingerprint_audio_propagates_generation_error(mock_fp_file: MagicMock) -> None:
    mock_fp_file.side_effect = acoustid.FingerprintGenerationError("fpcalc failed")
    with pytest.raises(acoustid.FingerprintGenerationError):
        fingerprint_audio(Path("/tmp/silent.wav"), _make_segment())
