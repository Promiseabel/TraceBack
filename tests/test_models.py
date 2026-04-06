"""Unit tests for models.py — dataclass definitions and PipelineResult logic."""

from __future__ import annotations

from tb.models import (
    PipelineResult,
    Segment,
    SegmentResult,
)


def _make_segment(index: int = 0, duration: float = 30.0) -> Segment:
    return Segment(index=index, start_time=0.0, end_time=duration, duration=duration)


def _make_segment_result(method: str = "no_match") -> SegmentResult:
    seg = _make_segment()
    result = SegmentResult(segment=seg, fingerprint=None)
    result.method = method  # type: ignore[assignment]
    return result


def test_segment_duration_field() -> None:
    seg = Segment(index=0, start_time=0.0, end_time=30.0, duration=30.0)
    assert seg.duration == 30.0


def test_pipeline_result_accuracy_empty() -> None:
    pr = PipelineResult(clip_path="test.mp4", total_segments=0)
    assert pr.accuracy == 0.0


def test_pipeline_result_accuracy_partial() -> None:
    pr = PipelineResult(
        clip_path="test.mp4",
        total_segments=3,
        matches=[
            _make_segment_result("audio"),
            _make_segment_result("visual"),
            _make_segment_result("no_match"),
        ],
    )
    assert abs(pr.accuracy - 2 / 3) < 1e-9


def test_pipeline_result_accuracy_full() -> None:
    pr = PipelineResult(
        clip_path="test.mp4",
        total_segments=2,
        matches=[
            _make_segment_result("audio"),
            _make_segment_result("audio"),
        ],
    )
    assert pr.accuracy == 1.0


def test_pipeline_result_matched_count_only_non_no_match() -> None:
    pr = PipelineResult(
        clip_path="test.mp4",
        total_segments=4,
        matches=[
            _make_segment_result("audio"),
            _make_segment_result("visual"),
            _make_segment_result("no_match"),
            _make_segment_result("no_match"),
        ],
    )
    assert pr.matched_count == 2


def test_pipeline_result_to_dict_structure() -> None:
    seg = _make_segment()
    sr = SegmentResult(segment=seg, fingerprint=None, source="Artist — Title", confidence=0.9)
    sr.method = "audio"  # type: ignore[assignment]
    pr = PipelineResult(clip_path="clip.mp4", total_segments=1, matches=[sr])

    d = pr.to_dict()
    assert d["clip_path"] == "clip.mp4"
    assert d["total_segments"] == 1
    assert d["matched_count"] == 1
    assert d["accuracy"] == 1.0
    assert isinstance(d["matches"], list)
    assert len(d["matches"]) == 1  # type: ignore[arg-type]

    entry = d["matches"][0]  # type: ignore[index]
    assert entry["segment_index"] == 0
    assert entry["method"] == "audio"
    assert entry["source"] == "Artist — Title"
    assert entry["confidence"] == 0.9


def test_segment_result_default_method() -> None:
    seg = _make_segment()
    sr = SegmentResult(segment=seg, fingerprint=None)
    assert sr.method == "no_match"


def test_pipeline_result_empty_matches_list() -> None:
    pr = PipelineResult(clip_path="empty.mp4", total_segments=0)
    assert pr.matches == []
    assert pr.matched_count == 0
    d = pr.to_dict()
    assert d["matches"] == []
