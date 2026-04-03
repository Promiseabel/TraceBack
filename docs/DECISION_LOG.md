# Decision Log — Traceback

**Version**: 1.0  
**Date**: 2026-04-03  
**Status**: Active

All architectural decisions are recorded here. Add a new entry whenever a significant decision
is made or revisited. Never delete entries — supersede them with a newer entry that references
the original.

---

## Entry 001 — Audio-First Matching Strategy

**Date**: 2026-04-03  
**Status**: Active

### Context
Traceback needs to identify the original source of edited video clips. Clips may be cropped,
resized, color-graded, letterboxed, or have text/watermarks overlaid. Two primary matching
signals are available: audio fingerprinting and visual perceptual hashing.

### Decision
Use audio fingerprinting (via Chromaprint/AcoustID) as the primary matching signal. Visual
pHash is a fallback stub for segments where audio matching fails or no audio is present.

### Rationale
Audio is far more resilient to the edits commonly applied to viral clips:
- Cropping/aspect ratio changes have zero impact on the audio stream
- Color grading, brightness/contrast, watermarks — all zero impact on audio
- Speed/pitch changes do degrade audio fingerprints, but these are less common edits
- AcoustID is a mature, free public service with a large index
Visual matching without a reference database is unsolvable for the PoC scope.

### Alternatives Considered
- **Visual-first**: Would require a reference video database and robust frame-level matching.
  Not feasible for a PoC without significant infrastructure.
- **Both signals, weighted**: More accurate but requires a reference database for visual
  matching to be meaningful. Deferred to post-PoC.

### Consequences
- Clips with no audio or heavily altered audio will not be attributed (returns `None`)
- AcoustID coverage gaps (tracks not in the index) are the primary failure mode
- Visual fallback is a stub — it computes a pHash but has no database to compare against

---

## Entry 002 — Segment-Level Matching (Not Whole-Clip)

**Date**: 2026-04-03  
**Status**: Active

### Context
Input clips may splice footage from multiple original source videos. A whole-clip fingerprint
would fail to attribute multi-source clips because the composite fingerprint would not match
any single source.

### Decision
Split input clips into segments at detected cut points before fingerprinting. Each segment is
fingerprinted and matched independently. Results are reported as `list[SegmentResult]`.

### Rationale
Multi-source clips are the core use case for Traceback. A single-clip fingerprint approach
would miss the multi-source case entirely. Segment-level matching generalizes to both
single-source (one segment) and multi-source (multiple segments) clips.

### Alternatives Considered
- **Whole-clip matching**: Simpler, lower API cost, but fails for multi-source clips.
- **Sliding window**: Would produce overlapping fingerprints and be expensive. Cut detection
  is more principled.

### Consequences
- Requires cut detection (PySceneDetect) before fingerprinting
- Sub-7s segments (below Chromaprint minimum) must be merged or skipped
- API call count = number of segments, not 1 per clip

---

## Entry 003 — PySceneDetect for Cut Detection

**Date**: 2026-04-03  
**Status**: Active

### Context
Segment-level matching (Entry 002) requires detecting edit/cut points in the input clip.
Multiple approaches exist: frame difference, histogram comparison, ML-based detectors.

### Decision
Use PySceneDetect 0.6.x with `ContentDetector(threshold=27.0)` for cut detection.

### Rationale
- PySceneDetect is the de facto Python library for scene detection
- `ContentDetector` uses HSV weighted frame differences — reliable for hard cuts
- Threshold 27.0 is the library default and appropriate for typical hard cuts
- `AdaptiveDetector` is available for clips with fast camera movement (two-pass, uses
  rolling average instead of fixed threshold)
- v0.6.x is the current stable API (`VideoManager` was removed in 0.6 — a breaking change
  from 0.5 that all code must respect)

### Alternatives Considered
- **FFmpeg scene filter**: `ffmpeg -vf "select=gt(scene\,0.3)"` — works but produces frame
  numbers, not timestamps; less Pythonic integration.
- **ML-based detection**: More accurate for gradual transitions but overkill for PoC;
  no obvious free Python library.
- **Fixed-interval segmentation**: Simple but produces arbitrary segments that may not align
  with actual edit points.

### Consequences
- `from scenedetect import VideoManager` must NEVER appear in any file — it is removed in 0.6
- Default threshold 27.0 may need tuning for unusual content
- Sub-7s segments after detection must be merged with adjacent segments in `segmenter.py`

---

## Entry 004 — AcoustID Confidence Threshold = 0.7

**Date**: 2026-04-03  
**Status**: Active

### Context
AcoustID returns a `score` field (float 0–1) for each result. A threshold must be chosen
above which a match is accepted as reliable attribution.

### Decision
Accept AcoustID results where `result["score"] >= 0.7`. Discard results below this threshold.

### Rationale
- Score 1.0 = perfect match. Scores 0.8–1.0 are high-confidence.
- 0.7 is a widely-used lower bound for AcoustID in production tools (e.g., beets music tagger)
- Below 0.7, false positive risk becomes significant (wrong source attribution is worse than
  no attribution)
- The field name in the AcoustID response is `"score"` — not `"confidence"` or `"probability"`.
  Do not confuse field names.

### Alternatives Considered
- **0.5 threshold**: More matches, more false positives. Rejected — wrong attribution is
  actively harmful to the use case.
- **0.9 threshold**: Fewer matches, fewer false positives. May miss valid matches for
  slightly degraded audio. Can be made configurable post-PoC.
- **No threshold (return all)**: Caller-controlled filtering. Deferred to post-PoC API design.

### Consequences
- Segments with score in [0.0, 0.7) will have `best_match = None` and `source = None`
- Audio-altered clips (pitch shift, speed change) may fall below threshold — expected behavior
- Threshold is hardcoded in `lookup.py`; make configurable in a future version

---

## Entry 005 — Minimum Fingerprint Segment Duration = 7 Seconds

**Date**: 2026-04-03  
**Status**: Active

### Context
Chromaprint (the algorithm underlying pyacoustid's `fingerprint_file()`) requires a minimum
audio duration to generate a reliable fingerprint. AcoustID matching degrades significantly
on very short clips.

### Decision
Enforce a minimum segment duration of 7 seconds. Segments shorter than 7 seconds must be
merged with an adjacent segment in `segmenter.py` before fingerprinting. If a merged segment
is still below 7 seconds, skip fingerprinting and log a warning.

### Rationale
- AcoustID documentation and community practice indicate that very short clips (under ~7s)
  produce unreliable fingerprints that frequently return false positives or no results
- 7 seconds is the practical lower bound observed in pyacoustid usage
- The `maxlength=120` parameter in `fingerprint_file()` caps the upper bound at 120 seconds

### Alternatives Considered
- **5 seconds**: Riskier — false positive rate increases. Rejected.
- **10 seconds**: Safer, but discards more valid clips. Can be tuned post-PoC.
- **No minimum**: Fingerprint everything and let AcoustID return empty. Wastes API quota.

### Consequences
- Some segments in heavily-edited clips may be merged, losing cut-point granularity
- If a clip consists entirely of sub-7s segments, the pipeline returns `SegmentResult`
  objects with `fingerprint=None` and `best_match=None`
- The minimum is checked in `segmenter.py` after `get_scene_list()`, not in `fingerprinter.py`

---

*Add new entries below this line. Use the format: Entry NNN — Title.*

---

## Entry 006 — Python Package Name: `tb` (not `traceback`)

**Date**: 2026-04-03  
**Status**: Active

### Context
During Phase 0 environment setup, all test collection failed with:
`ModuleNotFoundError: No module named 'traceback.extractor'; 'traceback' is not a package`
The root cause: Python's standard library contains a module named `traceback` (a single `.py`
file at `/usr/lib/python3.11/traceback.py`). When `import traceback.extractor` is attempted,
Python resolves `traceback` to the stdlib module (not our package) and fails.

### Decision
Rename the Python package from `traceback` to `tb` (short for Traceback).
All imports updated: `from tb.pipeline import run`, `python -m tb.pipeline`, etc.
The project name remains "Traceback" — only the importable Python package name changes.

### Rationale
`traceback` is a reserved stdlib module name. Any package with this name will fail to import
in any Python environment. Renaming is required, not optional.

### Alternatives Considered
- **Namespace package** (`traceback_project.pipeline`): Verbose and breaks the clean API.
- **src-only install trick**: Would not fix the stdlib collision.
- **`tracebackpipeline`**: Valid but long. `tb` is cleaner and unambiguous in this project.

### Consequences
- All imports use `from tb.xxx import ...`
- CLI entrypoint is `python -m tb.pipeline`
- CLAUDE.md, AGENTS.md, BUILD.md, all docs, all agent files updated
- pyproject.toml `name = "tb"`

---

## Entry 007 — Phase 0 Lint/Type Baseline

**Date**: 2026-04-03  
**Status**: Active

### Context
Phase 0 step 9 established the lint and type baseline before any pipeline logic was written.

### Findings
- **ruff**: 2 issues found, both auto-fixed:
  - `E501` — 1 line in extractor.py docstring exceeded 100 chars (ffmpeg command example)
  - `I001` — import block unsorted in visual.py (auto-fixed by `ruff --fix`)
- **mypy** (`--ignore-missing-imports`): 0 errors across all 8 source files

### Decision
Target state for all subsequent phases: ruff exits 0, mypy exits 0.
Phase 0 ended with both tools clean.
