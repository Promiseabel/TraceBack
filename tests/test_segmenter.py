"""Unit tests for segmenter.py — PySceneDetect 0.6.x cut detection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from traceback.models import Segment
from traceback.segmenter import MIN_SEGMENT_DURATION, detect_segments


def _make_timecode(seconds: float) -> MagicMock:
    tc = MagicMock()
    tc.get_seconds.return_value = seconds
    return tc


@patch("traceback.segmenter.SceneManager")
@patch("traceback.segmenter.open_video")
def test_detect_segments_two_cuts(mock_open_video: MagicMock, mock_scene_manager_cls: MagicMock) -> None:
    scene_manager = MagicMock()
    mock_scene_manager_cls.return_value = scene_manager
    # Two scenes: 0–10s, 10–25s
    scene_manager.get_scene_list.return_value = [
        (_make_timecode(0.0), _make_timecode(10.0)),
        (_make_timecode(10.0), _make_timecode(25.0)),
    ]
    segments = detect_segments(Path("/tmp/video.mp4"))
    assert len(segments) == 2
    assert segments[0].start_time == 0.0
    assert segments[0].end_time == 10.0
    assert segments[1].start_time == 10.0
    assert segments[1].end_time == 25.0
    assert segments[0].index == 0
    assert segments[1].index == 1


@patch("traceback.segmenter.SceneManager")
@patch("traceback.segmenter.open_video")
def test_no_cuts_returns_single_segment(mock_open_video: MagicMock, mock_scene_manager_cls: MagicMock) -> None:
    scene_manager = MagicMock()
    mock_scene_manager_cls.return_value = scene_manager
    scene_manager.get_scene_list.return_value = []
    # Second open_video call for duration
    video_mock = MagicMock()
    video_mock.duration.get_seconds.return_value = 30.0
    mock_open_video.side_effect = [MagicMock(), video_mock]
    segments = detect_segments(Path("/tmp/video.mp4"))
    assert len(segments) == 1
    assert segments[0].index == 0
    assert segments[0].start_time == 0.0


@patch("traceback.segmenter.SceneManager")
@patch("traceback.segmenter.open_video")
def test_short_segment_merged(mock_open_video: MagicMock, mock_scene_manager_cls: MagicMock) -> None:
    scene_manager = MagicMock()
    mock_scene_manager_cls.return_value = scene_manager
    # First segment is 3s (below 7s minimum) — should be merged with second
    scene_manager.get_scene_list.return_value = [
        (_make_timecode(0.0), _make_timecode(3.0)),
        (_make_timecode(3.0), _make_timecode(20.0)),
    ]
    segments = detect_segments(Path("/tmp/video.mp4"))
    assert len(segments) == 1
    assert segments[0].start_time == 0.0
    assert segments[0].end_time == 20.0


def test_videomanager_not_imported() -> None:
    """Guard: VideoManager must not be imported (removed in PySceneDetect 0.6)."""
    source = Path("src/traceback/segmenter.py").read_text()
    assert "VideoManager" not in source, (
        "VideoManager was removed in PySceneDetect 0.6 — must not be imported"
    )
