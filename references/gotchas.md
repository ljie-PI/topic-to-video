# Gotchas Catalog — Upstream Pipeline Pitfalls

This file is for `topic-to-video` upstream issues: research, harvest, TTS, ASR,
deterministic assets, and handoff contracts. HyperFrames composition, CSS, GSAP,
lint, inspect, and render implementation pitfalls belong to the `hyperframes`,
`hyperframes-cli`, and `gsap` skills.

## 1. Whisper / HyperFrames Transcribe for Chinese

Do not use Whisper or `npx hyperframes transcribe` for Chinese narration in
this workflow. Prior runs hit model-download failures and bad UTF-8 output.

Fix: use `scripts/transcribe-paraformer.py`, which calls DashScope
Paraformer-realtime-v2 and returns clean word-level timings.

If Paraformer is unavailable, ask the user for an external transcript rather
than silently switching to HyperFrames transcription.

## 2. Paraformer Sample Rate Mismatch

Symptom:

```text
status_code: 44
error: Failed to decode audio: sample rate 16000 not equals with real 22050
```

Root cause: Paraformer rejects audio whose declared sample rate differs from the
real file sample rate.

Fix: always probe with ffprobe before Recognition(). The shipped
`scripts/transcribe-paraformer.py` already does this.

## 3. CosyVoice Script Source Editing

Do not copy `voice-clone.py` and paste narration into Python source.
That makes resume and review fragile.

Fix: keep narration in `narration.txt` and call:

```bash
python3 scripts/voice-clone.py \
  --input-file {work_dir}/{topic_name}/narration.txt \
  --output-dir {work_dir}/{topic_name}/voice_clone \
  --speech-rate 1.2
```

Set the voice with `--voice` or `COSYVOICE_VOICE_ID`.

## 4. Full-Width Chinese Colon Can Add TTS Pauses

CosyVoice can occasionally insert a noticeable pause after `：` when it is
followed by a long compound sentence.

Fix: use `——`, commas, or split the sentence before generating TTS.

## 5. Gemini Deep Research UI Automation Is Fragile

`scripts/gemini-deep-research.py` automates a consumer web UI, so selector or
flow changes can break it.

Fix: if the script fails with a selector timeout, failed step, or runtime error,
fall back to targeted `web_search` research. Do not block the project on Gemini
UI automation.

## 6. MinerU Cloud Failures

MinerU cloud can fail for token, timeout, or URL-fetch reasons.

Fixes:
- Missing or failed cloud token: allow `parse-pdf.py` to fall back to local
  `mineru` when available.
- Cloud timeout on URL: download the PDF and retry with `--pdf`.
- Cloud error `-60007`: retry locally.

## 7. Chrome CDP Profile Lock

Chrome launches with a shared profile at `{work_dir}/chrome_profile/`. If
Chrome exits immediately, another Chrome process may already hold that profile.

Fix: close the conflicting Chrome process or pass a different `--profile-dir`.
If CDP port 9222 is busy, pass another `--cdp-url`, such as
`http://localhost:9223`.

## 8. Video Downloads Must Stay Sequential

YouTube/Bilibili downloads via yt-dlp are prone to throttling when run in
parallel.

Fix: iterate `manifest.pending_downloads[]` sequentially. If a download fails
because of geoblock, age gate, 410, or rate limit, leave `download_required:
true`; Phase 4 ignores unresolved clips.

## 9. Apply Video Download Results to Manifests

Downloading a video is not enough. Phase 4 reads `manifest.json` and per-slug
`metadata.json`.

Fix: after a successful `video-download.py` run, apply the result:

```bash
scripts/apply-video-download-result.py \
  --harvest-dir {work_dir}/{topic_name}/harvest_page/ \
  --source-slug "<item.source_slug>" \
  --url "<item.url>" \
  --result-json /path/to/video-download-result.json
```

## 10. Merge Parsed Papers Into the Harvest Manifest

`parse-pdf.py` writes `manifest_papers.json`, not the unified
`manifest.json`.

Fix: after paper parsing and web harvest, run:

```bash
scripts/merge-paper-manifest.py \
  --harvest-dir {work_dir}/{topic_name}/harvest_page/
```

## 11. Strip Source Audio From Video Clips

Material videos can contain their own narration, music, or UI sounds. The final
video should use `voice_clone/narration.mp3` as the only narration voice.

Fix: when cutting catalog video clips, use `-an` to remove source audio. This is
an upstream material contract passed to the HyperFrames sub-agent.

## 12. Use Python 3 in the Project Environment

Use `python3` after activating the project venv. Do not assume `python` points
to Python 3 on all machines.

Common fixes:
- `playwright` import error: `pip install playwright`
- `dashscope` import error: install the DashScope SDK in the venv
- `mineru` missing: `pip install "mineru[pipeline]"`
