# Business Requirements Document — Traceback

**Version**: 1.0  
**Date**: 2026-04-03  
**Status**: Active

---

## Problem Statement

Short-form video platforms (TikTok, Reels, YouTube Shorts) are saturated with clips that are
edited, cropped, spliced, or re-uploaded from original source material — often with overlaid
text, music, color grading, or aspect-ratio changes. There is currently no automated tool that
can take an arbitrary edited clip and identify the original video source(s) it was derived from,
or the timestamps within those originals where each segment appears.

This creates problems for:
- Content creators whose work is redistributed without attribution
- Journalists verifying the provenance of viral footage
- Platforms enforcing copyright or provenance policies

---

## Goal

Build a proof-of-concept Python pipeline that, given a short input clip, returns the original
video source and approximate timestamp per segment — analogous to how Shazam identifies music
from a short audio sample.

---

## Success Criteria

| Criterion | Target | Measurement |
|---|---|---|
| Single-source clip attribution | ≥80% correct AcoustID match | Run against 10 test clips with known sources |
| Multi-source splice attribution | ≥60% correct per-segment | Run against 5 spliced clips with known segment sources |
| Silent clip handling | Graceful fallback, no crash | pHash stub invoked without exception |
| Sub-7s segment handling | Segment merged or skipped with warning | No fingerprint attempt on <7s segments |
| Rate limit compliance | Zero AcoustID 429 errors | Enforce 3 req/sec in lookup.py |
| Type safety | mypy --strict passes with 0 errors | CI gate |
| Lint | ruff check exits 0 | CI gate |

---

## Scope

### In Scope

- Audio extraction from video (ffmpeg)
- Edit/cut point detection (PySceneDetect 0.6.x)
- Per-segment audio fingerprinting (Chromaprint via pyacoustid)
- AcoustID lookup for audio-based source attribution
- Visual pHash computation as fallback stub (imagehash)
- Per-segment `SegmentResult` output with source, confidence, timestamp
- CLI entrypoint: `python -m traceback.pipeline <clip>`

### Out of Scope (PoC)

- Visual-only matching against a reference video database
- Real-time or streaming processing
- Web UI or API server
- Support for video sources not indexed by AcoustID
- Proprietary or platform-specific matching (e.g., YouTube Content ID)
- Deduplication or clustering across multiple clips

---

## Stakeholders

- **Developer**: Builder and primary user of the PoC
- **Journalists / researchers**: Prospective users who need provenance verification tools

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| AcoustID coverage gaps (track not indexed) | High | High | Visual pHash fallback; log unmatched segments |
| Silent clips with no audio track | Medium | Medium | Detect silence; skip fingerprinting; invoke visual fallback |
| Sub-7s segments after cut detection | Medium | Medium | Merge adjacent short segments in segmenter.py |
| Audio-altered clips (pitch shift, speed change) | Medium | High | Log degraded confidence; mark as LOW_CONFIDENCE |
| AcoustID rate limit (3 req/sec) | Low | Medium | Enforce rate limit in lookup.py with time.sleep() |
| fpcalc not installed on target system | Medium | High | Pre-flight check in pipeline.py with clear error message |

---

## Constraints

- Python 3.11+ (union type syntax, dataclasses)
- Must work offline except for AcoustID API calls
- Must not store or cache user video content
- `ACOUSTID_API_KEY` must not be hardcoded — read from environment only

---

## Non-Functional Requirements

- Pipeline should complete a 60-second clip in under 60 seconds on commodity hardware
- Memory usage should not exceed 2GB for typical clips
- All failures should be logged with the failing module name and segment index

---

*Update this document when success criteria change, scope changes, or new risks are identified.*
