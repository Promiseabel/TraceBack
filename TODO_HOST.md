# Host TODO — Things Claude Cannot Do

These tasks require human action, physical access, external accounts, or real media files.
Everything in this file is a genuine blocker that cannot be automated.

---

## 1. Load the API Key in Your Shell Session

The key is stored in `.env` but the pipeline reads it from the environment, not the file.
Before running the pipeline, export it:

```bash
export $(cat .env | xargs)
```

Or add it to your shell profile so it persists across sessions.

---

## 2. Prepare Test Clips (Phase 3 — Evaluation)

The test suite is all unit tests with mocks. To run the evaluation matrix in
`docs/TEST_PLAN.md` you need real video clips. Claude cannot source, record, or
download media files.

### Category 1 — Single-Source Clips (need ≥3 clips, each ≥15s)
- Clips must be direct excerpts from a single original video with no modifications
- The original track must be indexed in AcoustID (mainstream/popular music works best;
  obscure or unlicensed tracks may return no results)
- You need to know the expected artist + title for each clip so you can verify the result

### Category 2 — Multi-Source Splice Clips (need ≥3 clips)
- Each clip must splice footage from 2 or more distinct original videos
- Each individual segment within the splice must be ≥7 seconds (Chromaprint minimum)
- You need a ground-truth mapping: segment N → source video title/artist
- Create these by concatenating known clips with ffmpeg:
  ```bash
  ffmpeg -i clip_a.mp4 -i clip_b.mp4 -filter_complex concat=n=2:v=1:a=1 splice.mp4
  ```

### Category 3 — Visual-Only Edits (need ≥2 clips)
- Take a clip from Category 1 and apply visual-only modifications:
  - Crop / change aspect ratio
  - Add a text watermark or overlay
  - Adjust brightness/contrast/saturation
  - Add letterbox bars
- Audio must remain untouched — this tests that visual edits don't break audio matching
- Tools: ffmpeg, DaVinci Resolve, CapCut, any video editor

### Category 4 — Silent Clips (need ≥2 clips)
- One clip with no audio stream at all:
  ```bash
  ffmpeg -i input.mp4 -an silent_no_stream.mp4
  ```
- One clip with an audio stream that is pure silence:
  ```bash
  ffmpeg -i input.mp4 -af "volume=0" silent_muted.mp4
  ```

### Category 5 — Audio-Altered Clips (need ≥2 clips)
- Take a Category 1 clip and modify the audio:
  - Pitch shift (±2–5 semitones): `ffmpeg -i input.mp4 -af "asetrate=44100*1.1" pitch.mp4`
  - Speed change (±10–20%): `ffmpeg -i input.mp4 -filter:a "atempo=1.15" speed.mp4`
  - Aggressive lossy compression: re-encode at very low bitrate (e.g. 32kbps mp3)
- You need the original clip's known source so you can verify degraded-but-correct vs wrong

---

## 3. Place Test Clips in a Known Location

Once you have clips, put them somewhere consistent so you can pass paths to the pipeline:

```bash
mkdir -p test_clips/{single_source,multi_source,visual_edits,silent,audio_altered}
# copy clips into appropriate subdirectories
```

Then run per category:
```bash
python -m tb.pipeline test_clips/single_source/clip1.mp4
```

---

## 4. Run the Evaluation and Update TEST_PLAN.md

After running clips against the pipeline, use the `test-evaluator` agent to tally results
and fill in the Results Log in `docs/TEST_PLAN.md`. The table rows currently read PENDING.

Target pass rates (from BRD):
- Single-source: ≥80% correctly attributed
- Multi-source: ≥60% of segments correctly attributed

---

## 5. Build a Visual Reference Database (Post-PoC, Optional)

`visual.py`'s `match_frame()` function accepts a `reference_db: dict[str, str]` (ref_id →
pHash hex string), but there is no database to populate it with. For the current PoC,
`best_match` is always `None` when audio fails and the clip has no AcoustID entry.

To make visual matching useful you would need to:
1. Collect reference frames from known source videos
2. Compute their pHash values with `compute_phash()`
3. Store the mapping (video title/ID → pHash) as a JSON file or database
4. Pass that mapping into `match_frame()` when calling the pipeline

This is explicitly out of scope for the PoC (see `docs/DECISION_LOG.md` Entry 001) but is
the natural next step if audio-only attribution is insufficient.

---

## 6. Register for AcoustID If the Key Expires

The API key in `.env` is tied to your AcoustID account. If it stops working:
- Log in at https://acoustid.org/login
- Go to "My Applications" and regenerate or create a new key
- Update the value in `.env`

---

## Summary

| # | Task | Blocking for |
|---|---|---|
| 1 | Export `ACOUSTID_API_KEY` in shell | Running the pipeline at all |
| 2 | Source test clips (5 categories) | Phase 3 evaluation |
| 3 | Place clips in `test_clips/` | Running evaluation commands |
| 4 | Run evaluation + update TEST_PLAN.md | Phase 3 exit criteria |
| 5 | Build visual reference database | Post-PoC visual matching |
| 6 | Renew AcoustID key if needed | Long-term operation |
