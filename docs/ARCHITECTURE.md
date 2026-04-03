# Technical Architecture — Traceback

**Version**: 1.0  
**Date**: 2026-04-03  
**Status**: Active

---

## Pipeline Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  INPUT: Path to video clip (any ffmpeg-supported format)        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Path
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  segmenter.detect_segments(video_path, threshold=27.0)          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ open_video(str(video_path))                             │   │
│  │ SceneManager + ContentDetector(threshold=27.0)          │   │
│  │ scene_manager.detect_scenes(video, show_progress=False) │   │
│  │ scene_manager.get_scene_list()                          │   │
│  │ → merge segments < 7s with neighbors                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ list[Segment]
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  For each Segment (in pipeline.py, using TemporaryDirectory):   │
│                                                                 │
│  extractor.extract_segment_audio(video_path, start, end, tmp)   │
│  → ffmpeg -i <video> -ss <start> -to <end>                      │
│           -acodec pcm_s16le -ac 2 -ar 44100 <tmp.wav>           │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Path (tmp WAV file)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  fingerprinter.fingerprint_audio(audio_path)                    │
│  → acoustid.fingerprint_file(path, maxlength=120)               │
│  → (duration: float, fingerprint: str)                          │
│  → FingerprintResult(segment, duration, fingerprint)            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ FingerprintResult
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  lookup.lookup_fingerprint(fp, api_key)                         │
│  POST https://api.acoustid.org/v2/lookup                        │
│  params: client, fingerprint, duration,                         │
│          meta=["recordings","releasegroups"]                     │
│  Rate limit: 3 req/sec enforced with time.sleep()               │
│  → filter results where result["score"] >= 0.7                  │
│  → list[AcoustIDMatch] (or [] if no match above threshold)      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │ match found?            │ no match (empty list)
              ▼                         ▼
┌─────────────────────┐   ┌─────────────────────────────────────┐
│ SegmentResult with  │   │ extractor.extract_frame(            │
│ best_match,         │   │   video_path, midpoint, tmp.png)    │
│ source, confidence  │   │ → ffmpeg -ss <t> -i <v> -frames:v 1 │
└─────────────────────┘   │ visual.compute_phash(tmp.png)        │
                          │ → imagehash.phash(PIL.Image.open())  │
                          │ → SegmentResult with visual_hash     │
                          │   (source=None, PoC stub)            │
                          └─────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  OUTPUT: list[SegmentResult]                                    │
│  Each: segment(index,start,end,duration), fingerprint,          │
│        matches, best_match, visual_hash, source, confidence     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Module Responsibilities

| Module | Responsibility | External I/O |
|---|---|---|
| `models.py` | Dataclass definitions — all inter-module data contracts | None |
| `extractor.py` | All ffmpeg subprocess calls — audio and frame extraction | ffmpeg (subprocess) |
| `segmenter.py` | PySceneDetect 0.6.x cut detection → list[Segment] | OpenCV (via scenedetect) |
| `fingerprinter.py` | pyacoustid fingerprint_file() → FingerprintResult | fpcalc (subprocess via pyacoustid) |
| `lookup.py` | AcoustID API calls, rate limiting, response parsing | AcoustID HTTPS API |
| `visual.py` | imagehash pHash computation and Hamming comparison | None |
| `pipeline.py` | Orchestrator — env vars, temp files, module sequencing | All above modules |

### Design Principles

- **extractor.py is the only ffmpeg caller** — no subprocess calls to ffmpeg elsewhere
- **lookup.py is the only network caller** — no HTTP requests in other modules
- **models.py defines all inter-module types** — no ad-hoc dicts between modules
- **pipeline.py manages temp files** — uses `tempfile.TemporaryDirectory` as context manager

---

## Data Models

```python
@dataclass
class Segment:
    index: int          # 0-based segment index
    start_time: float   # seconds from video start
    end_time: float     # seconds from video start
    duration: float     # end_time - start_time

@dataclass
class FingerprintResult:
    segment: Segment
    duration: float     # actual audio duration fingerprinted (from fpcalc)
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
    fingerprint: FingerprintResult | None   # None if segment too short (<7s)
    matches: list[AcoustIDMatch]            # all results with score >= 0.7
    best_match: AcoustIDMatch | None        # highest-score match, or None
    visual_hash: str | None                 # pHash string if fallback triggered
    source: str | None                      # "artist — title" or None
    confidence: float                       # best_match.score or 0.0
```

---

## External API Standards

### AcoustID Web Service

**Endpoint**: `https://api.acoustid.org/v2/lookup`  
**Method**: GET (pyacoustid builds query string)  
**Rate limit**: 3 requests per second

Required parameters:
| Param | Type | Value |
|---|---|---|
| `client` | string | `ACOUSTID_API_KEY` from environment |
| `fingerprint` | string | Chromaprint fingerprint string |
| `duration` | int | Audio duration in seconds |

Optional parameters used in this project:
| Param | Value |
|---|---|
| `meta` | `recordings releasegroups` |

Response shape (relevant fields only):
```json
{
  "status": "ok",
  "results": [
    {
      "id": "<acoustid-uuid>",
      "score": 0.98,
      "recordings": [
        {
          "id": "<musicbrainz-recording-id>",
          "title": "Track Title",
          "artists": [{"name": "Artist Name"}]
        }
      ]
    }
  ]
}
```

**Confidence field**: `results[n]["score"]` — do NOT use `"confidence"` or `"probability"`  
**Threshold**: `score >= 0.7`

### pyacoustid Call

```python
import acoustid
duration, fingerprint = acoustid.fingerprint_file(str(audio_path), maxlength=120)
response = acoustid.lookup(api_key, fingerprint, duration, meta=["recordings", "releasegroups"])
```

---

## Dependency Table

| Package | Version Pin | Purpose | System dep? |
|---|---|---|---|
| pyacoustid | >=1.3.0 | Chromaprint fingerprinting + AcoustID lookup | No |
| scenedetect[opencv] | >=0.6.0,<0.7.0 | Cut detection (0.6.x API — VideoManager removed) | No |
| ImageHash | >=4.3.1 | Perceptual hashing for visual fallback | No |
| Pillow | >=10.0.0 | PIL Image input required by imagehash.phash() | No |
| ffmpeg | any | Audio/frame extraction | Yes — must be on PATH |
| fpcalc | any | Chromaprint CLI (called by pyacoustid) | Yes — chromaprint-tools |
| pytest | >=8.0 | Test runner | No (dev) |
| ruff | >=0.4.0 | Linter | No (dev) |
| mypy | >=1.9.0 | Type checker | No (dev) |

---

*Update this document when the pipeline, modules, external APIs, or data models change.*
