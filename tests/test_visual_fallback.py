"""Unit tests for visual.py match_frame() — reference-db pHash matching."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import imagehash

from tb.models import Segment
from tb.visual import match_frame


def _make_segment() -> Segment:
    return Segment(index=0, start_time=0.0, end_time=15.0, duration=15.0)


def _hex_hash(value: int = 0) -> str:
    """Return a pHash hex string for a given integer (zero-padded to 16 hex chars)."""
    h = imagehash.ImageHash.__new__(imagehash.ImageHash)
    import numpy as np
    bits = 64
    arr = np.zeros(bits, dtype=bool)
    for i in range(bits):
        arr[i] = bool((value >> i) & 1)
    h.hash = arr.reshape((8, 8))
    return str(h)


@patch("tb.visual.compute_phash")
def test_match_frame_finds_near_duplicate(mock_phash: MagicMock) -> None:
    """When reference has same hash, method='visual' and confidence=1.0."""
    query_hex = _hex_hash(0)
    mock_phash.return_value = query_hex

    reference_db = {"ref_video_001": query_hex}
    seg = _make_segment()

    result = match_frame(Path("/tmp/frame.png"), reference_db, seg)

    assert result.method == "visual"
    assert result.source == "ref_video_001"
    assert result.confidence == 1.0
    assert result.visual_hash == query_hex


@patch("tb.visual.compute_phash")
def test_match_frame_rejects_different_image(mock_phash: MagicMock) -> None:
    """When best Hamming distance > LIKELY_MATCH_THRESHOLD, method='no_match'."""
    # All-zeros hash vs all-ones hash → Hamming distance = 64
    query_hex = _hex_hash(0)
    different_hex = _hex_hash((1 << 64) - 1)
    mock_phash.return_value = query_hex

    reference_db = {"ref_001": different_hex}
    seg = _make_segment()

    result = match_frame(Path("/tmp/frame.png"), reference_db, seg)

    assert result.method == "no_match"
    assert result.visual_hash == query_hex


@patch("tb.visual.compute_phash")
def test_match_frame_empty_db_returns_no_match(mock_phash: MagicMock) -> None:
    """Empty reference_db → no_match without error."""
    mock_phash.return_value = _hex_hash(0)
    seg = _make_segment()

    result = match_frame(Path("/tmp/frame.png"), {}, seg)

    assert result.method == "no_match"
    assert result.source is None


@patch("tb.visual.compute_phash")
def test_confidence_normalization_identical(mock_phash: MagicMock) -> None:
    """Hamming distance 0 → confidence 1.0."""
    h = _hex_hash(0)
    mock_phash.return_value = h
    seg = _make_segment()

    result = match_frame(Path("/tmp/frame.png"), {"ref": h}, seg)

    assert result.method == "visual"
    assert result.confidence == 1.0


@patch("tb.visual.compute_phash")
def test_match_frame_uses_pil_for_loading(mock_phash: MagicMock) -> None:
    """compute_phash (which opens PIL Image) is called with the frame path."""
    h = _hex_hash(0)
    mock_phash.return_value = h
    seg = _make_segment()
    frame = Path("/tmp/test_frame.png")

    match_frame(frame, {"ref": h}, seg)

    mock_phash.assert_called_once_with(frame)


@patch("tb.visual.compute_phash")
def test_match_frame_picks_closest_reference(mock_phash: MagicMock) -> None:
    """When multiple references exist, the closest (minimum distance) is chosen."""
    query_hex = _hex_hash(0)
    close_hex = _hex_hash(1)    # distance 1 from query
    far_hex = _hex_hash(255)    # distance 8 from query

    mock_phash.return_value = query_hex
    seg = _make_segment()

    reference_db = {"far_ref": far_hex, "close_ref": close_hex}
    result = match_frame(Path("/tmp/frame.png"), reference_db, seg)

    assert result.method == "visual"
    assert result.source == "close_ref"
