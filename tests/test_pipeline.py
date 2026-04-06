"""Unit tests for pipeline.py — top-level orchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import acoustid
import pytest

from tb.models import AcoustIDMatch, FingerprintResult, PipelineResult, Segment


def _make_segment(index: int = 0, duration: float = 15.0) -> Segment:
    return Segment(index=index, start_time=0.0, end_time=duration, duration=duration)


def _make_fp(seg: Segment) -> FingerprintResult:
    return FingerprintResult(segment=seg, duration=12.5, fingerprint="AQAA")


def _make_match(score: float = 0.95) -> AcoustIDMatch:
    return AcoustIDMatch(
        recording_id="abc-123",
        title="Test Track",
        artist="Test Artist",
        score=score,
    )


@patch("tb.pipeline.compute_phash")
@patch("tb.pipeline.extract_frame")
@patch("tb.pipeline.lookup_fingerprint")
@patch("tb.pipeline.fingerprint_audio")
@patch("tb.pipeline.extract_segment_audio")
@patch("tb.pipeline.detect_segments")
def test_pipeline_happy_path(
    mock_detect: MagicMock,
    mock_extract_audio: MagicMock,
    mock_fingerprint: MagicMock,
    mock_lookup: MagicMock,
    mock_extract_frame: MagicMock,
    mock_phash: MagicMock,
    tmp_path: Path,
) -> None:
    seg = _make_segment()
    fp = _make_fp(seg)
    match = _make_match()

    mock_detect.return_value = [seg]
    mock_extract_audio.return_value = tmp_path / "seg_0.wav"
    mock_fingerprint.return_value = fp
    mock_lookup.return_value = [match]

    video = tmp_path / "video.mp4"
    video.touch()

    from tb.pipeline import run
    pipeline_result = run(video, api_key="test_key")

    assert isinstance(pipeline_result, PipelineResult)
    assert len(pipeline_result.matches) == 1
    r = pipeline_result.matches[0]
    assert r.best_match is match
    assert r.source == "Test Artist — Test Track"
    assert r.confidence == 0.95
    assert r.method == "audio"
    mock_extract_frame.assert_not_called()  # no visual fallback needed


@patch("tb.pipeline.compute_phash")
@patch("tb.pipeline.extract_frame")
@patch("tb.pipeline.lookup_fingerprint")
@patch("tb.pipeline.fingerprint_audio")
@patch("tb.pipeline.extract_segment_audio")
@patch("tb.pipeline.detect_segments")
def test_pipeline_silent_clip_triggers_visual_fallback(
    mock_detect: MagicMock,
    mock_extract_audio: MagicMock,
    mock_fingerprint: MagicMock,
    mock_lookup: MagicMock,
    mock_extract_frame: MagicMock,
    mock_phash: MagicMock,
    tmp_path: Path,
) -> None:
    seg = _make_segment()
    mock_detect.return_value = [seg]
    mock_extract_audio.return_value = tmp_path / "seg_0.wav"
    mock_fingerprint.side_effect = acoustid.FingerprintGenerationError("silent")
    mock_phash.return_value = "f8f0e0c0808080c0"

    video = tmp_path / "video.mp4"
    video.touch()

    from tb.pipeline import run
    pipeline_result = run(video, api_key="test_key")

    assert isinstance(pipeline_result, PipelineResult)
    assert len(pipeline_result.matches) == 1
    r = pipeline_result.matches[0]
    assert r.best_match is None
    assert r.visual_hash == "f8f0e0c0808080c0"
    assert r.confidence == 0.0
    assert r.method == "visual"
    mock_extract_frame.assert_called_once()


def test_pipeline_raises_without_api_key(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.touch()

    import os
    env_backup = os.environ.pop("ACOUSTID_API_KEY", None)
    try:
        from tb.pipeline import run
        with pytest.raises(ValueError, match="ACOUSTID_API_KEY"):
            run(video, api_key=None)
    finally:
        if env_backup:
            os.environ["ACOUSTID_API_KEY"] = env_backup


def test_pipeline_raises_for_missing_file() -> None:
    from tb.pipeline import run
    with pytest.raises(FileNotFoundError):
        run(Path("/nonexistent/video.mp4"), api_key="test_key")


@patch("tb.pipeline.compute_phash")
@patch("tb.pipeline.extract_frame")
@patch("tb.pipeline.lookup_fingerprint")
@patch("tb.pipeline.fingerprint_audio")
@patch("tb.pipeline.extract_segment_audio")
@patch("tb.pipeline.detect_segments")
def test_pipeline_result_accuracy(
    mock_detect: MagicMock,
    mock_extract_audio: MagicMock,
    mock_fingerprint: MagicMock,
    mock_lookup: MagicMock,
    mock_extract_frame: MagicMock,
    mock_phash: MagicMock,
    tmp_path: Path,
) -> None:
    """PipelineResult.accuracy reflects the matched fraction."""
    seg = _make_segment()
    fp = _make_fp(seg)
    match = _make_match()

    mock_detect.return_value = [seg]
    mock_extract_audio.return_value = tmp_path / "seg_0.wav"
    mock_fingerprint.return_value = fp
    mock_lookup.return_value = [match]

    video = tmp_path / "video.mp4"
    video.touch()

    from tb.pipeline import run
    pipeline_result = run(video, api_key="test_key")

    assert pipeline_result.total_segments == 1
    assert pipeline_result.matched_count == 1
    assert pipeline_result.accuracy == 1.0
