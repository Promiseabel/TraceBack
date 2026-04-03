"""AcoustID web service lookup.

This is the ONLY module in the pipeline that makes network calls.
Enforces the AcoustID rate limit of 3 requests per second.

AcoustID API reference (confirmed):
  Endpoint: https://api.acoustid.org/v2/lookup
  Required params: client, fingerprint, duration
  Optional params: meta (values: recordings, releasegroups, etc.)
  Confidence field: result["score"] — float 0.0–1.0
  DO NOT USE: result["confidence"] or result["probability"] — those fields do not exist.
  Rate limit: 3 requests per second.
"""

from __future__ import annotations

import logging
import time

import acoustid

from traceback.models import AcoustIDMatch, FingerprintResult

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD: float = 0.7
_RATE_LIMIT_DELAY: float = 1.0 / 3.0  # enforce 3 requests per second


def lookup_fingerprint(fp: FingerprintResult, api_key: str) -> list[AcoustIDMatch]:
    """Look up a Chromaprint fingerprint against the AcoustID web service.

    Sleeps _RATE_LIMIT_DELAY seconds before each call to enforce 3 req/sec.
    Returns only results where result["score"] >= CONFIDENCE_THRESHOLD (0.7).
    Returns an empty list on API errors (logs a warning, does not raise).

    Args:
        fp: FingerprintResult containing the fingerprint string and duration.
        api_key: AcoustID API key (value of ACOUSTID_API_KEY env var).

    Returns:
        List of AcoustIDMatch objects above the confidence threshold,
        sorted by score descending. Empty list if no matches.
    """
    time.sleep(_RATE_LIMIT_DELAY)

    try:
        response = acoustid.lookup(
            api_key,
            fp.fingerprint,
            fp.duration,
            meta=["recordings", "releasegroups"],
        )
    except acoustid.WebServiceError as exc:
        logger.warning(
            "AcoustID API error for segment %d: %s", fp.segment.index, exc
        )
        return []

    if response.get("status") != "ok":
        logger.warning(
            "AcoustID returned non-ok status for segment %d: %s",
            fp.segment.index, response.get("status"),
        )
        return []

    matches: list[AcoustIDMatch] = []
    for result in response.get("results", []):
        score: float = float(result.get("score", 0.0))
        if score < CONFIDENCE_THRESHOLD:
            continue

        recordings = result.get("recordings", [])
        if not recordings:
            continue

        recording = recordings[0]
        artists = recording.get("artists", [])
        artist_name = artists[0].get("name", "") if artists else ""

        matches.append(
            AcoustIDMatch(
                recording_id=recording.get("id", ""),
                title=recording.get("title", ""),
                artist=artist_name,
                score=score,
            )
        )

    matches.sort(key=lambda m: m.score, reverse=True)
    logger.debug(
        "Segment %d: %d matches above threshold %.1f",
        fp.segment.index, len(matches), CONFIDENCE_THRESHOLD,
    )
    return matches
