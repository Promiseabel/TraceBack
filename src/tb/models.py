"""Data models — all inter-module data contracts for the Traceback pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


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
    method: Literal["audio", "visual", "no_match"] = "no_match"  # how match was found


@dataclass
class PipelineResult:
    """Aggregated pipeline output for a full clip."""

    clip_path: str
    total_segments: int
    matches: list[SegmentResult] = field(default_factory=list)

    @property
    def matched_count(self) -> int:
        """Number of segments matched by any method."""
        return sum(1 for m in self.matches if m.method != "no_match")

    @property
    def accuracy(self) -> float:
        """Fraction of segments successfully matched (0.0 if no segments)."""
        if self.total_segments == 0:
            return 0.0
        return self.matched_count / self.total_segments

    def to_dict(self) -> dict[str, object]:
        """Serialize to a plain dict suitable for JSON output."""
        return {
            "clip_path": self.clip_path,
            "total_segments": self.total_segments,
            "matched_count": self.matched_count,
            "accuracy": self.accuracy,
            "matches": [
                {
                    "segment_index": m.segment.index,
                    "start_time": m.segment.start_time,
                    "end_time": m.segment.end_time,
                    "duration": m.segment.duration,
                    "method": m.method,
                    "source": m.source,
                    "confidence": m.confidence,
                    "visual_hash": m.visual_hash,
                }
                for m in self.matches
            ],
        }
