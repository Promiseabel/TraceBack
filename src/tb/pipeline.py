"""Top-level pipeline orchestrator for Traceback.

Reads ACOUSTID_API_KEY from environment, manages temporary files,
and sequences all module calls in order:
  segmenter → extractor → fingerprinter → lookup → visual fallback (if needed)

CLI usage:
  python -m tb.pipeline <path_to_clip>
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from pathlib import Path

import acoustid

from tb.extractor import ExtractionError, extract_frame, extract_segment_audio
from tb.fingerprinter import fingerprint_audio
from tb.lookup import lookup_fingerprint
from tb.models import PipelineResult, SegmentResult
from tb.segmenter import MIN_SEGMENT_DURATION, detect_segments
from tb.visual import compute_phash

logger = logging.getLogger(__name__)


def run(video_path: Path, api_key: str | None = None) -> PipelineResult:
    """Run the full Traceback pipeline against a video clip.

    Steps:
      1. Detect cut points → list[Segment]
      2. For each segment:
         a. Extract audio WAV
         b. Fingerprint with Chromaprint
         c. Look up against AcoustID (score >= 0.7)
         d. If no match: extract keyframe, compute pHash (fallback stub)
      3. Return PipelineResult

    Args:
        video_path: Path to the input video clip.
        api_key: AcoustID API key. If None, reads ACOUSTID_API_KEY from environment.

    Returns:
        PipelineResult with per-segment SegmentResult objects and summary stats.

    Raises:
        ValueError: If no AcoustID API key is available.
        FileNotFoundError: If video_path does not exist.
    """
    if api_key is None:
        api_key = os.environ.get("ACOUSTID_API_KEY")
    if not api_key:
        raise ValueError(
            "ACOUSTID_API_KEY not set. "
            "Copy .env.example to .env and set your AcoustID API key. "
            "Get a free key at: https://acoustid.org/login"
        )

    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    logger.info("Running Traceback pipeline on: %s", video_path.name)
    segments = detect_segments(video_path)
    logger.info("Detected %d segment(s)", len(segments))

    results: list[SegmentResult] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)

        for seg in segments:
            result = SegmentResult(segment=seg, fingerprint=None)

            if seg.duration < MIN_SEGMENT_DURATION:
                logger.warning(
                    "Segment %d is %.1fs (< %.1fs minimum); skipping fingerprint",
                    seg.index, seg.duration, MIN_SEGMENT_DURATION,
                )
                results.append(result)
                continue

            # Extract segment audio
            wav_path = tmp / f"seg_{seg.index}.wav"
            try:
                extract_segment_audio(video_path, seg.start_time, seg.end_time, wav_path)
            except ExtractionError as exc:
                logger.warning("Audio extraction failed for segment %d: %s", seg.index, exc)
                results.append(result)
                continue

            # Fingerprint
            try:
                fp = fingerprint_audio(wav_path, seg)
                result.fingerprint = fp
            except acoustid.FingerprintGenerationError as exc:
                logger.warning(
                    "No audio or silent audio in segment %d: %s", seg.index, exc
                )
                # Fall through to visual fallback

            # AcoustID lookup (only if fingerprint succeeded)
            if result.fingerprint is not None:
                matches = lookup_fingerprint(result.fingerprint, api_key)
                result.matches = matches
                if matches:
                    best = matches[0]
                    result.best_match = best
                    result.source = f"{best.artist} — {best.title}" if best.artist else best.title
                    result.confidence = best.score
                    result.method = "audio"
                else:
                    logger.warning(
                        "Low confidence match for segment %d: no results above %.1f",
                        seg.index, 0.7,
                    )

            # Visual fallback if no audio match
            if result.best_match is None:
                midpoint = seg.start_time + seg.duration / 2
                frame_path = tmp / f"seg_{seg.index}_frame.png"
                try:
                    extract_frame(video_path, midpoint, frame_path)
                    result.visual_hash = compute_phash(frame_path)
                    result.method = "visual"
                    logger.debug(
                        "Visual fallback for segment %d: phash=%s",
                        seg.index, result.visual_hash,
                    )
                except Exception as exc:
                    logger.warning(
                        "Visual fallback failed for segment %d: %s", seg.index, exc
                    )

            results.append(result)

    logger.info("Pipeline complete: %d result(s)", len(results))
    return PipelineResult(
        clip_path=str(video_path),
        total_segments=len(segments),
        matches=results,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m tb.pipeline <path_to_clip>")
        sys.exit(1)

    clip = Path(sys.argv[1])
    pipeline_result = run(clip)

    print(f"\nTraceback results for: {clip.name}")
    print("-" * 60)
    for r in pipeline_result.matches:
        seg = r.segment
        status = r.source or ("VISUAL_HASH" if r.visual_hash else "UNMATCHED")
        print(
            f"  Segment {seg.index:02d}  "
            f"{seg.start_time:6.1f}s – {seg.end_time:6.1f}s  "
            f"({seg.duration:.1f}s)  →  {status}  "
            f"[confidence={r.confidence:.2f}]  [{r.method}]"
        )
    print(f"\nAccuracy: {pipeline_result.accuracy:.0%} "
          f"({pipeline_result.matched_count}/{pipeline_result.total_segments} matched)")
