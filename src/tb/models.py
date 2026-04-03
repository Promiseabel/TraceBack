"""Data models — all inter-module data contracts for the Traceback pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Segment:
    """A detected segment within the input clip, defined by start/end times."""

    index: int
    start_time: float  # seconds from video start
    end_time: float  # seconds from video start
    duration: float  # end_time - start_time


@dataclass
class FingerprintResult:
    """Raw Chromaprint fingerprint output for a single segment."""

    segment: Segment
    duration: float  # actual audio duration fingerprinted (from fpcalc)
    fingerprint: str  # raw Chromaprint string


@dataclass
class AcoustIDMatch:
    """A single AcoustID result above the confidence threshold.

    The score field corresponds to result["score"] in the AcoustID API response.
    Confidence threshold: score >= 0.7 (see lookup.py CONFIDENCE_THRESHOLD).
    """

    recording_id: str  # MusicBrainz recording ID
    title: str
    artist: str
    score: float  # 0.0–1.0 from AcoustID response["results"][n]["score"]


@dataclass
class SegmentResult:
    """Per-segment attribution result — the final output unit of the pipeline."""

    segment: Segment
    fingerprint: FingerprintResult | None  # None if segment too short (<7s)
    matches: list[AcoustIDMatch] = field(default_factory=list)  # all above threshold
    best_match: AcoustIDMatch | None = None  # highest-score match, or None
    visual_hash: str | None = None  # pHash hex string if visual fallback triggered
    source: str | None = None  # "artist — title" or None if unmatched
    confidence: float = 0.0  # best_match.score or 0.0
