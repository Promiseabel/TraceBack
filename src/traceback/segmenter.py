"""Cut detection using PySceneDetect 0.6.x.

IMPORTANT: VideoManager was removed in PySceneDetect 0.6. This module uses the
open_video() + SceneManager pattern exclusively. Never import VideoManager.

Segments shorter than MIN_SEGMENT_DURATION (7 seconds) are merged with adjacent
segments before returning, because Chromaprint requires a minimum duration for
reliable fingerprints.
"""

from __future__ import annotations

import logging
from pathlib import Path

from scenedetect import SceneManager, open_video
from scenedetect.detectors import ContentDetector

from traceback.models import Segment

logger = logging.getLogger(__name__)

MIN_SEGMENT_DURATION: float = 7.0  # seconds — Chromaprint constraint


def detect_segments(video_path: Path, threshold: float = 27.0) -> list[Segment]:
    """Detect edit/cut points and return a list of Segments.

    Uses PySceneDetect 0.6.x ContentDetector with a fixed threshold.
    Merges segments shorter than MIN_SEGMENT_DURATION with their successor
    (or predecessor for the last segment).

    Args:
        video_path: Path to the input video file.
        threshold: ContentDetector sensitivity. Lower = more sensitive to cuts.
                   Default 27.0 is the PySceneDetect library default.

    Returns:
        List of Segment objects (0-indexed), each with start_time, end_time,
        duration in seconds. Always returns at least one Segment.
    """
    video = open_video(str(video_path))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))
    scene_manager.detect_scenes(video, show_progress=False)
    scene_list = scene_manager.get_scene_list()

    if not scene_list:
        # No cuts detected — treat entire video as one segment
        video2 = open_video(str(video_path))
        total = video2.duration.get_seconds() if video2.duration else 0.0
        logger.info("No cuts detected in %s; treating as single segment", video_path.name)
        return [Segment(index=0, start_time=0.0, end_time=total, duration=total)]

    # Convert FrameTimecode pairs to raw (start, end) float tuples
    raw: list[tuple[float, float]] = [
        (scene[0].get_seconds(), scene[1].get_seconds())
        for scene in scene_list
    ]

    # Merge segments shorter than MIN_SEGMENT_DURATION
    merged = _merge_short_segments(raw)

    return [
        Segment(
            index=i,
            start_time=start,
            end_time=end,
            duration=round(end - start, 3),
        )
        for i, (start, end) in enumerate(merged)
    ]


def _merge_short_segments(
    segments: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Merge segments shorter than MIN_SEGMENT_DURATION with their successor."""
    if not segments:
        return segments

    result: list[tuple[float, float]] = []
    i = 0
    while i < len(segments):
        start, end = segments[i]
        duration = end - start
        if duration < MIN_SEGMENT_DURATION and i + 1 < len(segments):
            # Merge with next segment
            next_end = segments[i + 1][1]
            logger.debug(
                "Merging short segment %.1fs–%.1fs (%.1fs) with next",
                start, end, duration,
            )
            segments[i + 1] = (start, next_end)
            i += 1
            continue
        result.append((start, end))
        i += 1

    return result
