# Traceback — Claude Code Project Context

Traceback is a Python 3.11+ proof-of-concept pipeline that identifies the original source of
edited or clipped video content. Given a short input clip (which may splice footage from
multiple originals), it returns the original video source and approximate timestamp per segment.

## Pipeline Overview

```
Input clip
    │
    ├─ [extractor.py]     ffmpeg → full audio WAV
    │
    ├─ [segmenter.py]     PySceneDetect 0.6.x → list of Segments (start/end times)
    │
    ├─ [extractor.py]     ffmpeg → per-segment audio WAV (≥7s minimum)
    │
    ├─ [fingerprinter.py] pyacoustid → FingerprintResult per segment
    │
    ├─ [lookup.py]        AcoustID API → list[AcoustIDMatch] (score ≥ 0.7)
    │
    └─ [visual.py]        imagehash pHash fallback (if audio match fails)
```

## Commands

```bash
# Run tests
python -m pytest tests/ -v

# Lint
python -m ruff check src/ tests/

# Type check
python -m mypy src/ --strict

# Run pipeline on a clip
python -m tb.pipeline <path_to_clip>

# Via slash command
/run-pipeline <path_to_clip>
```

## Environment

Copy `.env.example` to `.env` and fill in your key:
```
ACOUSTID_API_KEY=<your_key>
```
Get a free API key at: https://acoustid.org/login

## Version Pins (critical — do not change without updating AGENTS.md)

| Package | Pin | Reason |
|---|---|---|
| scenedetect | >=0.6.0,<0.7.0 | VideoManager was removed in 0.6; API is stable within 0.6.x |
| pyacoustid | >=1.3.0 | fingerprint_file() signature |
| ImageHash | >=4.3.1 | phash() PIL requirement |
| Python | >=3.11 | union type syntax (`X \| Y`), dataclasses |

**WARNING**: Do NOT use `VideoManager` from PySceneDetect — it was removed in 0.6.
Use `open_video()` + `SceneManager` instead.

## Subagents

| Agent | Invoke when |
|---|---|
| `pipeline-runner` | Running or debugging the pipeline end-to-end |
| `test-evaluator` | After code changes — runs pytest, updates TEST_PLAN.md |
| `refactor-reviewer` | Before commits — ruff, mypy, API standard checks |

## Living Documents — MUST Stay Updated

These four documents must be updated whenever the relevant area changes.
Never let them go stale. Update them as part of the same commit as code changes.

| Document | Update when |
|---|---|
| `docs/BRD.md` | Requirements or success criteria change |
| `docs/ARCHITECTURE.md` | Pipeline, modules, or external APIs change |
| `docs/TEST_PLAN.md` | New test categories added; results logged after each test run |
| `docs/DECISION_LOG.md` | Any architectural decision is made or revisited |

## Key Architectural Decisions

See `docs/DECISION_LOG.md` for full rationale. Summary:

- **Audio-first**: More resilient to cropping, overlays, aspect ratio changes than visual matching
- **Segment-level**: Multi-source clips require per-segment attribution, not whole-clip
- **AcoustID threshold**: 0.7 (confidence field is `score` in the API response)
- **Min segment duration**: 7 seconds (Chromaprint constraint for reliable fingerprints)
- **PySceneDetect only for cut detection** — not content matching

## Module Responsibilities

| Module | Responsibility |
|---|---|
| `models.py` | Dataclass definitions — Segment, FingerprintResult, AcoustIDMatch, SegmentResult |
| `extractor.py` | All ffmpeg subprocess calls — audio and frame extraction |
| `segmenter.py` | PySceneDetect 0.6.x cut detection → list[Segment] |
| `fingerprinter.py` | pyacoustid fingerprint_file() → FingerprintResult |
| `lookup.py` | AcoustID API calls, rate limiting, response parsing |
| `visual.py` | imagehash pHash computation and comparison (PoC stub) |
| `pipeline.py` | Top-level orchestrator — reads ACOUSTID_API_KEY, manages temp files |
