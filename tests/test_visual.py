"""Unit tests for visual.py — imagehash pHash computation and comparison."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import imagehash
import pytest

from traceback.visual import NEAR_DUPLICATE_THRESHOLD, compare_phash, compute_phash


@patch("traceback.visual.imagehash.phash")
@patch("traceback.visual.Image.open")
def test_compute_phash_returns_string(mock_open: MagicMock, mock_phash: MagicMock) -> None:
    mock_phash.return_value = imagehash.hex_to_hash("f8f0e0c0808080c0")
    result = compute_phash(Path("/tmp/frame.png"))
    assert isinstance(result, str)
    assert len(result) > 0


@patch("traceback.visual.imagehash.phash")
@patch("traceback.visual.Image.open")
def test_compute_phash_opens_image_not_passes_path(mock_open: MagicMock, mock_phash: MagicMock) -> None:
    """Guard: imagehash.phash() must receive PIL Image, not a path string."""
    mock_phash.return_value = imagehash.hex_to_hash("f8f0e0c0808080c0")
    compute_phash(Path("/tmp/frame.png"))
    mock_open.assert_called_once()
    # phash must be called with the return value of Image.open, not the path
    phash_arg = mock_phash.call_args[0][0]
    assert phash_arg is mock_open.return_value


def test_compare_phash_identical_hashes_zero_distance() -> None:
    h = "f8f0e0c0808080c0"
    assert compare_phash(h, h) == 0


def test_compare_phash_different_hashes_nonzero() -> None:
    h1 = "f8f0e0c0808080c0"
    h2 = "0000000000000000"
    dist = compare_phash(h1, h2)
    assert dist > NEAR_DUPLICATE_THRESHOLD


def test_compare_phash_returns_int() -> None:
    h1 = "f8f0e0c0808080c0"
    h2 = "f8f0e0c0808080ff"
    result = compare_phash(h1, h2)
    assert isinstance(result, int)
    assert 0 <= result <= 64
