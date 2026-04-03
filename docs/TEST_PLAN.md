# Test Plan & Evaluation Matrix — Traceback

**Version**: 1.0  
**Date**: 2026-04-03  
**Status**: Active — Results Log to be filled as tests are run

---

## Overview

Tests are organized into two layers:
1. **Unit tests** (`tests/`) — per-module, use mocks/fixtures, fast
2. **Evaluation matrix** (this document) — end-to-end test categories against real clips

The `test-evaluator` agent runs pytest after every code change and updates the Results Log.

---

## Test Categories & Pass Criteria

### Category 1: Single-Source Clip

**Description**: Input clip is a direct excerpt from one original video with no modifications.

**Test clips**: At least 3 clips of known provenance, each ≥15 seconds.

**Pass criteria**:
- AcoustID `score` for the correct match is `>= 0.7`
- `best_match.recording_id` is correct
- `best_match.title` and `best_match.artist` are non-empty
- Pipeline returns exactly 1 `SegmentResult` (no false cut detected)
- Overall success rate: **≥ 80%** of test clips correctly attributed

**Failure signals**:
- `score < 0.7` — track not in AcoustID, or audio too degraded
- Multiple SegmentResults with wrong cut points

---

### Category 2: Multi-Source Splice

**Description**: Input clip splices footage from 2+ original videos. Each splice is ≥7 seconds.

**Test clips**: At least 3 spliced clips with known segment-to-source mapping.

**Pass criteria**:
- `segmenter.detect_segments()` returns the correct number of segments (±1)
- Each segment's `best_match` corresponds to the correct source video
- Each `best_match.score >= 0.7`
- Overall success rate: **≥ 60%** of segments correctly attributed across test clips

**Failure signals**:
- Missed cuts — segments merged incorrectly
- Wrong source attribution on a segment

---

### Category 3: Visual-Only Edits

**Description**: Input clip has the same audio as original but with visual modifications:
color grading, aspect ratio change, letterboxing, watermarks, brightness/contrast adjustment.

**Test clips**: At least 2 clips with known original, visually modified.

**Pass criteria**:
- Audio fingerprint is unaffected by visual edits
- `best_match.score >= 0.7` (same threshold as single-source)
- Attribution is identical to the unmodified version

**Rationale**: Audio-first design means visual edits should have zero impact. If this category
fails, it indicates an audio extraction problem (e.g., re-encoding introduced artifacts).

---

### Category 4: Silent Clips

**Description**: Input clip has no audio track, or the audio is silence throughout.

**Test clips**: At least 2 clips (one with no audio stream, one with silent audio).

**Pass criteria**:
- Pipeline does NOT raise an exception
- `fingerprint` field in `SegmentResult` is `None`
- `visual_hash` is populated (pHash fallback triggered)
- A warning is logged: `"No audio or silent audio in segment {index}"`
- `best_match` is `None` (PoC does not have a visual reference database)
- `confidence` is `0.0`

**Failure signals**:
- Exception raised when fpcalc receives silence
- No fallback to visual path

---

### Category 5: Audio-Altered Clips

**Description**: Input clip has audio that has been modified: pitch-shifted, time-stretched,
speed-changed, or compressed with aggressive codec settings.

**Test clips**: At least 2 clips with known originals, audio-modified.

**Pass criteria**:
- Pipeline completes without exception
- If `score < 0.7`: `best_match` is `None` and warning logged: `"Low confidence match for segment {index}: score={score:.2f}"`
- If `score >= 0.7` despite alteration: attribution is still correct (bonus)
- No silent failure — all results have either a match or explicit `None` with log

**Rationale**: Chromaprint is resilient to mild alterations but degrades with aggressive changes.
This category tests graceful degradation.

---

## Unit Test Coverage Map

| Test File | Module Under Test | Key Test Cases |
|---|---|---|
| `test_extractor.py` | `extractor.py` | Happy path WAV output; time-bounded segment; keyframe extraction; missing ffmpeg raises error |
| `test_segmenter.py` | `segmenter.py` | Single-cut video → 2 segments; no-cut video → 1 segment; sub-7s merge; VideoManager not imported |
| `test_fingerprinter.py` | `fingerprinter.py` | Happy path returns FingerprintResult; short audio raises/warns; fpcalc not installed error |
| `test_lookup.py` | `lookup.py` | Happy path returns list[AcoustIDMatch]; score < 0.7 filtered out; API error returns []; rate limit enforced |
| `test_visual.py` | `visual.py` | phash returns string; same image distance=0; different images distance>5; PIL Image required (not path) |
| `test_pipeline.py` | `pipeline.py` | End-to-end with mocked modules; ACOUSTID_API_KEY missing raises; temp files cleaned up; silent clip fallback |

---

## Results Log

*Filled by the `test-evaluator` agent after each test run. Never edit manually.*

| Date | Category | Passed | Total | Status | Notes |
|---|---|---|---|---|---|
| — | single-source | — | — | PENDING | Not yet run |
| — | multi-source splice | — | — | PENDING | Not yet run |
| — | visual-only edits | — | — | PENDING | Not yet run |
| — | silent clips | — | — | PENDING | Not yet run |
| — | audio-altered | — | — | PENDING | Not yet run |

### Unit Test Run History

| Date | Passed | Failed | Errors | Notes |
|---|---|---|---|---|
| — | — | — | — | Not yet run |

---

*Update this document when new test categories are added or pass criteria change. The Results
Log is updated automatically by the `test-evaluator` agent.*
