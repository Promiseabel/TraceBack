"""Audio fingerprinting via pyacoustid (Chromaprint).

Wraps acoustid.fingerprint_file() which invokes fpcalc under the hood.
This module does not make any network calls — all network I/O is in lookup.py.

pyacoustid signature (confirmed):
    duration, fingerprint = acoustid.fingerprint_file(path, maxlength=120)
    Returns: (float, str) — duration first, fingerprint second.

Minimum reliable segment duration: 7 seconds (MIN_SEGMENT_DURATION in segmenter.py).
"""

from __future__ import annotations

import logging
from pathlib import Path

import acoustid

from tb.models import FingerprintResult, Segment

logger = logging.getLogger(__name__)


def fingerprint_audio(audio_path: Path, segment: Segment) -> FingerprintResult:
    """Generate a Chromaprint fingerprint for an audio file.

    Calls acoustid.fingerprint_file(str(audio_path), maxlength=120).
    The maxlength=120 caps fingerprinting at 120 seconds of audio.

    Args:
        audio_path: Path to a PCM WAV audio file.
        segment: The Segment this audio was extracted from (for result context).

    Returns:
        FingerprintResult with the segment, duration, and fingerprint string.

    Raises:
        acoustid.FingerprintGenerationError: If fpcalc fails, is not installed,
            or the audio file is empty/silent.
    """
    duration, fingerprint = acoustid.fingerprint_file(
        str(audio_path),
        maxlength=120,
    )
    logger.debug(
        "Fingerprinted segment %d: duration=%.2fs fingerprint=%s...",
        segment.index, duration, fingerprint[:16],
    )
    return FingerprintResult(
        segment=segment,
        duration=float(duration),
        fingerprint=str(fingerprint),
    )
