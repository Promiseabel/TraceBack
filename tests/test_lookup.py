"""Unit tests for lookup.py — AcoustID web service calls."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import acoustid
import pytest

from traceback.lookup import CONFIDENCE_THRESHOLD, lookup_fingerprint
from traceback.models import AcoustIDMatch, FingerprintResult, Segment


def _make_fp() -> FingerprintResult:
    seg = Segment(index=0, start_time=0.0, end_time=15.0, duration=15.0)
    return FingerprintResult(segment=seg, duration=12.5, fingerprint="AQAAUFqkMVmyJMHW")


def _make_acoustid_response(score: float = 0.98) -> dict:
    return {
        "status": "ok",
        "results": [
            {
                "id": "9ff43b6a-4f16-427c-93c2-92307ca505e0",
                "score": score,
                "recordings": [
                    {
                        "id": "38035858-f990-4fbb-b3b2-f2f8b958eeba",
                        "title": "Test Track",
                        "artists": [{"name": "Test Artist"}],
                    }
                ],
            }
        ],
    }


@patch("traceback.lookup.time.sleep")
@patch("traceback.lookup.acoustid.lookup")
def test_lookup_happy_path(mock_lookup: MagicMock, mock_sleep: MagicMock) -> None:
    mock_lookup.return_value = _make_acoustid_response(score=0.98)
    matches = lookup_fingerprint(_make_fp(), "test_api_key")
    assert len(matches) == 1
    assert matches[0].title == "Test Track"
    assert matches[0].artist == "Test Artist"
    assert matches[0].score == 0.98
    assert isinstance(matches[0], AcoustIDMatch)


@patch("traceback.lookup.time.sleep")
@patch("traceback.lookup.acoustid.lookup")
def test_low_score_filtered_out(mock_lookup: MagicMock, mock_sleep: MagicMock) -> None:
    mock_lookup.return_value = _make_acoustid_response(score=0.5)
    matches = lookup_fingerprint(_make_fp(), "test_api_key")
    assert matches == []


@patch("traceback.lookup.time.sleep")
@patch("traceback.lookup.acoustid.lookup")
def test_api_error_returns_empty_list(mock_lookup: MagicMock, mock_sleep: MagicMock) -> None:
    mock_lookup.side_effect = acoustid.WebServiceError("connection refused")
    matches = lookup_fingerprint(_make_fp(), "test_api_key")
    assert matches == []


@patch("traceback.lookup.time.sleep")
@patch("traceback.lookup.acoustid.lookup")
def test_rate_limit_sleep_called(mock_lookup: MagicMock, mock_sleep: MagicMock) -> None:
    mock_lookup.return_value = _make_acoustid_response()
    lookup_fingerprint(_make_fp(), "test_api_key")
    mock_sleep.assert_called_once()
    delay = mock_sleep.call_args[0][0]
    # Should be ~0.333 seconds (1/3)
    assert abs(delay - (1.0 / 3.0)) < 0.01


@patch("traceback.lookup.time.sleep")
@patch("traceback.lookup.acoustid.lookup")
def test_uses_score_field_not_confidence(mock_lookup: MagicMock, mock_sleep: MagicMock) -> None:
    """Guard: confidence field must be 'score', not 'confidence' or 'probability'."""
    source = Path("src/traceback/lookup.py").read_text()
    assert '"score"' in source or "'score'" in source
    assert '"confidence"' not in source
    assert '"probability"' not in source
