# AGENTS.md — Traceback Universal Agent Standards

This file is tool-agnostic. It applies to Claude Code, Cursor, Copilot, Gemini CLI, Codex,
and any other AI coding agent working on this repository.

## Project

**Traceback** — Python 3.11+ pipeline that identifies the original source of edited/clipped
video content. Per-segment audio fingerprinting with visual pHash fallback.

Language: Python 3.11+  
Linter: ruff  
Type checker: mypy --strict  
Test runner: pytest

---

## AcoustID Web Service

**Endpoint**: `https://api.acoustid.org/v2/lookup`

**Required parameters**:
| Parameter | Type | Description |
|---|---|---|
| `client` | string | Your AcoustID API key (env: `ACOUSTID_API_KEY`) |
| `fingerprint` | string | Chromaprint fingerprint string from fpcalc/pyacoustid |
| `duration` | int | Audio duration in seconds |

**Optional parameters**:
| Parameter | Values | Description |
|---|---|---|
| `meta` | `recordings`, `recordingids`, `releases`, `releasegroups`, `releasegroupids`, `tracks` | Metadata to include in response |

**Response shape**:
```json
{
  "status": "ok",
  "results": [
    {
      "id": "9ff43b6a-4f16-427c-93c2-92307ca505e0",
      "score": 0.98,
      "recordings": [
        {
          "id": "38035858-f990-4fbb-b3b2-f2f8b958eeba",
          "title": "Track Title",
          "duration": 639,
          "artists": [{"id": "...", "name": "Artist Name"}],
          "releasegroups": [{"id": "...", "type": "Album", "title": "Album Title"}]
        }
      ]
    }
  ]
}
```

**Confidence field**: `result["score"]` — float 0.0–1.0. Do NOT use `"confidence"` or
`"probability"` — those fields do not exist in the AcoustID response.

**Confidence threshold**: `score >= 0.7` (project standard)

**Rate limit**: 3 requests per second. The `lookup.py` module enforces this. Do not bypass it.

---

## pyacoustid — Function Signatures

```python
import acoustid

# Fingerprint an audio file
# Returns: (duration: float, fingerprint: str)
duration, fingerprint = acoustid.fingerprint_file(
    path,           # str or Path — audio file to fingerprint
    maxlength=120,  # int — max seconds of audio to use (default 120)
)

# Look up a fingerprint against AcoustID
# Returns: dict — parsed JSON response (see response shape above)
results = acoustid.lookup(
    apikey,        # str — AcoustID API key
    fingerprint,   # str — Chromaprint fingerprint string
    duration,      # float — audio duration in seconds
    meta=["recordings", "releasegroups"],  # list[str] — optional metadata
)
```

`fingerprint_file()` calls `fpcalc` under the hood. `fpcalc` must be installed on the system.

---

## fpcalc CLI

**JSON output format**:
```json
{"duration": 12.60, "fingerprint": "AQAAUFqkMVmyJMHWBa97..."}
```

**Minimum reliable duration**: 7 seconds. Segments shorter than 7 seconds should be merged
with adjacent segments before fingerprinting.

**Direct invocation** (for debugging):
```bash
fpcalc -json <audio_file>
```

---

## PySceneDetect 0.6.x

**CRITICAL BREAKING CHANGE**: `VideoManager` was removed in v0.6. Any code using
`VideoManager` is incompatible with 0.6.x and must not be added.

**Correct imports**:
```python
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector, AdaptiveDetector
```

**Correct usage pattern** (v0.6.x only):
```python
video = open_video(str(video_path))
scene_manager = SceneManager()
scene_manager.add_detector(ContentDetector(threshold=27.0))
scene_manager.detect_scenes(video, show_progress=False)
scene_list = scene_manager.get_scene_list()
# scene_list: list of (FrameTimecode, FrameTimecode) tuples
# Access seconds: scene[0].get_seconds(), scene[1].get_seconds()
```

**ContentDetector threshold**: 27.0 (project default). Lower = more sensitive to cuts.

**AdaptiveDetector**: Two-pass detector. Use when source video has fast camera movement,
pans, or zooms that would cause false positives with a fixed threshold.

**DO NOT USE** (v0.5 patterns — incompatible):
```python
# WRONG — VideoManager removed in 0.6
from scenedetect import VideoManager
video_manager = VideoManager([video_path])
```

---

## imagehash — pHash

```python
import imagehash
from PIL import Image

# Input MUST be a PIL Image object — not a file path string
img = Image.open(str(image_path))
h = imagehash.phash(img)   # returns Hash object

# Comparing hashes — subtraction returns Hamming distance
dist = h1 - h2  # int, range 0–64
```

**Hamming distance thresholds**:
| Distance | Interpretation |
|---|---|
| 0 | Identical |
| 1–5 | Near-duplicate |
| 6–10 | Likely match |
| >10 | Probably different |

**Project threshold for near-duplicate**: `<= 5`

---

## ffmpeg Commands

All ffmpeg calls are in `extractor.py`. Use these exact flag sets.

**Extract full audio as PCM WAV**:
```bash
ffmpeg -i <video> -vn -acodec pcm_s16le -ac 2 -ar 44100 <output.wav>
```

**Extract time-bounded audio segment**:
```bash
ffmpeg -i <video> -ss <start_seconds> -to <end_seconds> -acodec pcm_s16le -ac 2 -ar 44100 <output.wav>
```

**Extract single keyframe at timestamp** (`-ss` before `-i` for fast seeking):
```bash
ffmpeg -ss <timestamp_seconds> -i <video> -frames:v 1 <output.png>
```

Flags reference:
- `-vn` — disable video stream
- `-acodec pcm_s16le` — PCM signed 16-bit little-endian
- `-ac 2` — stereo (2 channels)
- `-ar 44100` — 44.1 kHz sample rate
- `-frames:v 1` — extract exactly 1 video frame

---

## Data Models (src/traceback/models.py)

```python
@dataclass
class Segment:
    index: int
    start_time: float   # seconds from video start
    end_time: float     # seconds from video start
    duration: float     # end_time - start_time

@dataclass
class FingerprintResult:
    segment: Segment
    duration: float     # actual audio duration fingerprinted
    fingerprint: str    # raw Chromaprint string

@dataclass
class AcoustIDMatch:
    recording_id: str   # MusicBrainz recording ID
    title: str
    artist: str
    score: float        # 0.0–1.0 from AcoustID "score" field

@dataclass
class SegmentResult:
    segment: Segment
    fingerprint: FingerprintResult | None
    matches: list[AcoustIDMatch]        # all matches above threshold
    best_match: AcoustIDMatch | None    # highest-score match
    visual_hash: str | None             # pHash string if fallback triggered
    source: str | None                  # attributed source string
    confidence: float                   # 0.0–1.0
```

---

## Function Signatures (src/traceback/)

```python
# extractor.py
def extract_full_audio(video_path: Path, output_path: Path) -> Path: ...
def extract_segment_audio(video_path: Path, start: float, end: float, output_path: Path) -> Path: ...
def extract_frame(video_path: Path, timestamp: float, output_path: Path) -> Path: ...

# segmenter.py
def detect_segments(video_path: Path, threshold: float = 27.0) -> list[Segment]: ...

# fingerprinter.py
def fingerprint_audio(audio_path: Path) -> FingerprintResult: ...

# lookup.py
def lookup_fingerprint(fp: FingerprintResult, api_key: str) -> list[AcoustIDMatch]: ...

# visual.py
def compute_phash(image_path: Path) -> str: ...
def compare_phash(h1: str, h2: str) -> int: ...

# pipeline.py
def run(video_path: Path, api_key: str | None = None) -> list[SegmentResult]: ...
```

---

## Environment

Required: `ACOUSTID_API_KEY` environment variable (or in `.env` file).

```bash
# .env
ACOUSTID_API_KEY=your_key_here
```

---

## Dependency Versions

| Package | Pin | Notes |
|---|---|---|
| Python | >=3.11 | Union type syntax, dataclasses |
| pyacoustid | >=1.3.0 | fingerprint_file() signature stable |
| scenedetect | >=0.6.0,<0.7.0 | 0.6.x API; VideoManager removed |
| ImageHash | >=4.3.1 | phash() with PIL Image input |
| Pillow | >=10.0.0 | PIL Image for imagehash input |
| ffmpeg | system dep | Must be on PATH |
| fpcalc | system dep | Part of chromaprint-tools package |
