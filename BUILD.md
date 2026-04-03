# BUILD.md — Traceback Implementation Guide

This is the authoritative phased build guide for implementing Traceback. Follow phases in
order. Each phase has clear entry criteria and exit criteria.

All API signatures, parameters, and standards are confirmed — see `AGENTS.md` for the
canonical reference. Do not invent alternatives.

---

## Phase 0: Environment Setup

### 0.1 System Dependencies

Install ffmpeg and chromaprint-tools (provides `fpcalc`):

```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg chromaprint-tools

# macOS
brew install ffmpeg chromaprint
```

Verify both are on PATH:
```bash
ffmpeg -version
fpcalc -version
```

### 0.2 Python Environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 0.3 Environment Variables

```bash
cp .env.example .env
# Edit .env and set ACOUSTID_API_KEY
# Get a free key at: https://acoustid.org/login
```

Load in shell (or use python-dotenv):
```bash
export $(cat .env | xargs)
```

### 0.4 Verify Setup

```bash
python -c "import acoustid, scenedetect, imagehash; print('deps OK')"
python -m pytest tests/ -v   # should collect tests (may skip if fixtures missing)
```

### Exit Criteria for Phase 0
- [ ] `ffmpeg -version` exits 0
- [ ] `fpcalc -version` exits 0
- [ ] `python -c "import acoustid, scenedetect, imagehash"` exits 0
- [ ] `.env` contains a valid `ACOUSTID_API_KEY`

---

## Phase 1: Module Scaffolding

Build modules in dependency order: `models.py` first, then `extractor.py`,
`segmenter.py`, `fingerprinter.py`, `lookup.py`, `visual.py`, then `pipeline.py` last.

### 1.1 models.py

Define all dataclasses. No imports from other `traceback` modules.

```python
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class Segment:
    index: int
    start_time: float   # seconds from video start
    end_time: float     # seconds from video start
    duration: float     # end_time - start_time

@dataclass
class FingerprintResult:
    segment: Segment
    duration: float     # actual audio duration from fpcalc
    fingerprint: str    # raw Chromaprint string

@dataclass
class AcoustIDMatch:
    recording_id: str   # MusicBrainz recording ID
    title: str
    artist: str
    score: float        # 0.0–1.0 from AcoustID response["results"][n]["score"]

@dataclass
class SegmentResult:
    segment: Segment
    fingerprint: FingerprintResult | None
    matches: list[AcoustIDMatch] = field(default_factory=list)
    best_match: AcoustIDMatch | None = None
    visual_hash: str | None = None
    source: str | None = None
    confidence: float = 0.0
```

### 1.2 extractor.py

All ffmpeg calls. Uses `subprocess.run(..., check=True)` — raises on non-zero exit.
Converts `Path` to `str` for subprocess arguments.

```python
from pathlib import Path
import subprocess

def extract_full_audio(video_path: Path, output_path: Path) -> Path:
    """Extract full audio track as PCM WAV.
    
    ffmpeg -i <video> -vn -acodec pcm_s16le -ac 2 -ar 44100 <output>
    Raises subprocess.CalledProcessError on ffmpeg failure.
    Returns output_path.
    """
    ...

def extract_segment_audio(
    video_path: Path,
    start: float,
    end: float,
    output_path: Path,
) -> Path:
    """Extract time-bounded audio segment as PCM WAV.
    
    ffmpeg -i <video> -ss <start> -to <end> -acodec pcm_s16le -ac 2 -ar 44100 <output>
    start and end are seconds (float).
    Raises subprocess.CalledProcessError on ffmpeg failure.
    Returns output_path.
    """
    ...

def extract_frame(video_path: Path, timestamp: float, output_path: Path) -> Path:
    """Extract single keyframe at timestamp as PNG.
    
    ffmpeg -ss <timestamp> -i <video> -frames:v 1 <output>
    Note: -ss before -i for fast seeking.
    Raises subprocess.CalledProcessError on ffmpeg failure.
    Returns output_path.
    """
    ...
```

**ffmpeg flag reference** (must match exactly):
```bash
# Full audio
ffmpeg -i <video> -vn -acodec pcm_s16le -ac 2 -ar 44100 <output.wav>

# Segment audio
ffmpeg -i <video> -ss <start> -to <end> -acodec pcm_s16le -ac 2 -ar 44100 <output.wav>

# Keyframe (-ss BEFORE -i)
ffmpeg -ss <timestamp> -i <video> -frames:v 1 <output.png>
```

### 1.3 segmenter.py

Uses PySceneDetect 0.6.x. **`VideoManager` must never appear here.**

```python
from pathlib import Path
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector
from traceback.models import Segment

MIN_SEGMENT_DURATION: float = 7.0  # seconds — Chromaprint constraint

def detect_segments(video_path: Path, threshold: float = 27.0) -> list[Segment]:
    """Detect cut points using PySceneDetect 0.6.x ContentDetector.
    
    Uses open_video() + SceneManager pattern (VideoManager is removed in 0.6).
    Merges segments shorter than MIN_SEGMENT_DURATION with the next segment.
    
    Returns list of Segment objects, each with:
      - index: 0-based
      - start_time: seconds
      - end_time: seconds  
      - duration: end_time - start_time
    
    If no cuts detected, returns a single Segment spanning the full video.
    """
    video = open_video(str(video_path))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))
    scene_manager.detect_scenes(video, show_progress=False)
    scene_list = scene_manager.get_scene_list()
    # scene_list: list of (FrameTimecode, FrameTimecode) tuples
    # Access seconds: scene[0].get_seconds(), scene[1].get_seconds()
    ...
```

**Merge logic**: After getting `scene_list`, iterate and merge any segment with
`duration < MIN_SEGMENT_DURATION` into the following segment (or previous if it's the last).

### 1.4 fingerprinter.py

Thin wrapper around pyacoustid. Does not call any network service.

```python
from pathlib import Path
import acoustid
from traceback.models import Segment, FingerprintResult

def fingerprint_audio(audio_path: Path) -> FingerprintResult:
    """Fingerprint an audio file using Chromaprint via pyacoustid.
    
    Calls acoustid.fingerprint_file(str(audio_path), maxlength=120)
    which invokes fpcalc under the hood.
    
    Returns FingerprintResult with:
      - duration: float (from fpcalc output)
      - fingerprint: str (raw Chromaprint string)
    
    Raises acoustid.FingerprintGenerationError if fpcalc fails or file is silent.
    The segment field is set by the caller (pipeline.py).
    """
    duration, fingerprint = acoustid.fingerprint_file(
        str(audio_path),
        maxlength=120,
    )
    ...
```

Note: `fingerprint_file()` returns `(duration: float, fingerprint: str)` — duration is first.

### 1.5 lookup.py

The ONLY module that makes network calls. Enforces 3 req/sec rate limit.

```python
from pathlib import Path
import time
import acoustid
from traceback.models import FingerprintResult, AcoustIDMatch

CONFIDENCE_THRESHOLD: float = 0.7
RATE_LIMIT_DELAY: float = 1.0 / 3.0  # 3 requests per second

def lookup_fingerprint(fp: FingerprintResult, api_key: str) -> list[AcoustIDMatch]:
    """Look up a fingerprint against the AcoustID web service.
    
    Endpoint: https://api.acoustid.org/v2/lookup
    Required params: client, fingerprint, duration
    Optional params: meta=["recordings", "releasegroups"]
    
    Confidence field in response: result["score"] (float 0–1)
    Returns only results where score >= CONFIDENCE_THRESHOLD (0.7).
    
    Returns [] on API error (logs warning, does not raise).
    Sleeps RATE_LIMIT_DELAY seconds before each call to enforce 3 req/sec.
    """
    time.sleep(RATE_LIMIT_DELAY)
    try:
        response = acoustid.lookup(
            api_key,
            fp.fingerprint,
            fp.duration,
            meta=["recordings", "releasegroups"],
        )
    except acoustid.WebServiceError as exc:
        # log warning, return []
        ...
    
    matches = []
    for result in response.get("results", []):
        score = result.get("score", 0.0)
        if score < CONFIDENCE_THRESHOLD:
            continue
        # Parse result["recordings"][0] for title and artist
        ...
    return matches
```

**Response field reference** (from AGENTS.md):
- Confidence: `result["score"]` — do NOT use `result["confidence"]`
- Recording: `result["recordings"][0]["title"]`, `result["recordings"][0]["artists"][0]["name"]`
- Recording ID: `result["recordings"][0]["id"]`

### 1.6 visual.py

PoC stub. Computes pHash but has no reference database to compare against.

```python
from pathlib import Path
import imagehash
from PIL import Image

NEAR_DUPLICATE_THRESHOLD: int = 5  # Hamming distance <= 5

def compute_phash(image_path: Path) -> str:
    """Compute perceptual hash of an image.
    
    Input MUST be opened as PIL Image — imagehash.phash() requires PIL Image, not path.
    Returns hash as hex string.
    """
    img = Image.open(str(image_path))
    h = imagehash.phash(img)
    return str(h)

def compare_phash(h1: str, h2: str) -> int:
    """Compare two pHash strings, returning Hamming distance (0–64).
    
    Distance 0 = identical
    Distance <= 5 = near-duplicate (NEAR_DUPLICATE_THRESHOLD)
    Distance <= 10 = likely match
    Distance > 10 = probably different
    
    Uses imagehash subtraction operator: hash1 - hash2 returns int.
    """
    ih1 = imagehash.hex_to_hash(h1)
    ih2 = imagehash.hex_to_hash(h2)
    return ih1 - ih2
```

### 1.7 pipeline.py

Top-level orchestrator. Manages temp files, reads API key, sequences module calls.

```python
from __future__ import annotations
import logging
import os
import tempfile
from pathlib import Path

from traceback.extractor import extract_segment_audio, extract_frame
from traceback.fingerprinter import fingerprint_audio
from traceback.lookup import lookup_fingerprint
from traceback.models import SegmentResult
from traceback.segmenter import detect_segments
from traceback.visual import compute_phash

logger = logging.getLogger(__name__)

def run(video_path: Path, api_key: str | None = None) -> list[SegmentResult]:
    """Run the full Traceback pipeline against a video clip.
    
    Reads ACOUSTID_API_KEY from environment if api_key is not provided.
    Raises ValueError if no API key is available.
    
    Manages a single TemporaryDirectory for all per-segment temp files.
    Calls modules in order: segmenter → extractor → fingerprinter → lookup → visual fallback.
    
    Returns list[SegmentResult], one per detected segment.
    """
    if api_key is None:
        api_key = os.environ.get("ACOUSTID_API_KEY")
    if not api_key:
        raise ValueError("ACOUSTID_API_KEY not set. Copy .env.example to .env and fill in your key.")
    
    segments = detect_segments(video_path)
    results: list[SegmentResult] = []
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        for seg in segments:
            # ... extract, fingerprint, lookup, fallback
            ...
    
    return results
```

**CLI entrypoint** (`if __name__ == "__main__"`):
```python
import sys
from pathlib import Path
from traceback.pipeline import run

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m traceback.pipeline <path_to_clip>")
        sys.exit(1)
    results = run(Path(sys.argv[1]))
    for r in results:
        print(f"Segment {r.segment.index} ({r.segment.start_time:.1f}s–{r.segment.end_time:.1f}s): "
              f"{r.source or 'UNMATCHED'} (confidence={r.confidence:.2f})")
```

### Exit Criteria for Phase 1
- [ ] All 7 modules exist with correct imports
- [ ] `from scenedetect import VideoManager` does not appear anywhere in `src/`
- [ ] `ruff check src/` exits 0
- [ ] `mypy src/ --strict` exits 0 (stubs may use `...` bodies)

---

## Phase 2: Tests

Write unit tests for each module. Use `unittest.mock` or `pytest-mock` to avoid network
calls and ffmpeg/fpcalc dependencies in unit tests.

### 2.1 test_extractor.py

```python
# Happy path: mock subprocess.run, verify correct ffmpeg args
# Error path: subprocess.CalledProcessError raised and propagated
# Verify: -ss before -i in keyframe extraction
# Verify: -vn -acodec pcm_s16le -ac 2 -ar 44100 in audio extraction
```

### 2.2 test_segmenter.py

```python
# Happy path: mock scene_manager.get_scene_list() returning 2 scenes → 2 Segments
# No-cut path: single scene → 1 Segment spanning full video
# Merge path: segment with duration < 7.0 merged with neighbor
# Guard: assert "VideoManager" not in open("src/traceback/segmenter.py").read()
```

### 2.3 test_fingerprinter.py

```python
# Happy path: mock acoustid.fingerprint_file() returning (12.0, "AQAA...") → FingerprintResult
# Error path: acoustid.FingerprintGenerationError raised and propagated
# Verify: maxlength=120 passed to fingerprint_file()
```

### 2.4 test_lookup.py

```python
# Happy path: mock acoustid.lookup() returning results with score=0.98 → list[AcoustIDMatch]
# Threshold path: result with score=0.5 filtered out → empty list
# API error path: acoustid.WebServiceError → return [] (no raise)
# Rate limit: assert time.sleep called with ~0.333 seconds
```

### 2.5 test_visual.py

```python
# compute_phash happy path: mock PIL Image.open, mock imagehash.phash → returns string
# compare_phash same hash: distance = 0
# compare_phash different hashes: distance > 0
# Verify: Image.open() called (not imagehash.phash receiving path string directly)
```

### 2.6 test_pipeline.py

```python
# End-to-end mock: mock all modules, verify call order
# Missing API key: ValueError raised with clear message
# Temp directory cleanup: TemporaryDirectory used as context manager
# Silent clip fallback: fingerprinter raises → visual fallback invoked
# Output shape: returns list[SegmentResult] with correct segment indices
```

### Exit Criteria for Phase 2
- [ ] `python -m pytest tests/ -v` — all tests collected and passing
- [ ] No test imports `VideoManager` from scenedetect
- [ ] No test makes real network calls to AcoustID
- [ ] No test invokes real ffmpeg or fpcalc

---

## Phase 3: Evaluation

Run the pipeline against real test clips to evaluate against the test matrix in
`docs/TEST_PLAN.md`. Update the Results Log after each run.

### 3.1 Prepare Test Clips

For each category in `TEST_PLAN.md`, prepare test clips with known provenance:
- Single-source: 3+ clips, each ≥15s, from AcoustID-indexed sources
- Multi-source splice: 3+ clips, known segment-to-source mapping
- Visual edits: 2+ clips (color-graded, letterboxed, watermarked)
- Silent: 2+ clips (no audio, or pure silence)
- Audio-altered: 2+ clips (pitch-shifted, speed-changed)

### 3.2 Run Evaluation

```bash
for clip in test_clips/*.mp4; do
    python -m traceback.pipeline "$clip"
done
```

### 3.3 Update TEST_PLAN.md

Use the `test-evaluator` agent to:
1. Tally results per category
2. Compare against pass criteria in `TEST_PLAN.md`
3. Update the Results Log table

### Exit Criteria for Phase 3
- [ ] Results Log in `docs/TEST_PLAN.md` populated for all 5 categories
- [ ] Single-source success rate ≥ 80% or documented gap with explanation
- [ ] All categories have a result (PASS / FAIL / PARTIAL), not PENDING

---

## Phase 4: Polish

### 4.1 Code Quality

```bash
python -m ruff check src/ tests/ --fix
python -m mypy src/ --strict
```

Resolve all violations. No `# noqa` suppressions without justification.

### 4.2 Update Living Documents

Before final commit, verify all four docs are current:

| Document | What to check |
|---|---|
| `docs/BRD.md` | Success criteria reflect actual measured results |
| `docs/ARCHITECTURE.md` | Module responsibilities match final implementation |
| `docs/TEST_PLAN.md` | Results Log is complete; pass criteria are accurate |
| `docs/DECISION_LOG.md` | Any decisions made during implementation are recorded |

### 4.3 Final Verification

```bash
# All tests pass
python -m pytest tests/ -v

# Clean lint
python -m ruff check src/ tests/

# Clean types
python -m mypy src/ --strict

# Pipeline runs
python -m traceback.pipeline <test_clip>
```

### Exit Criteria for Phase 4
- [ ] `pytest` all passing
- [ ] `ruff check` exits 0
- [ ] `mypy --strict` exits 0
- [ ] All 4 living docs updated
- [ ] No TODOs or placeholder `...` bodies remaining in `src/`
- [ ] `DECISION_LOG.md` has entries for any decisions made during Phases 1–3
