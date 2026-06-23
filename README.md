# Speaker Scribe

Speaker Scribe is a local-first web app for turning audio files into transcripts with speaker turns. It uses an Apple Silicon-friendly stack: `whispermlx` for Whisper transcription through MLX and pyannote-backed diarization when a Hugging Face token is available.

## What It Does

- Upload WAV, MP3, M4A, FLAC, or AAC audio files.
- Run local MLX Whisper transcription through `whispermlx`.
- Optionally run speaker diarization and word-to-speaker assignment.
- Estimate how many speakers are present.
- Let the user rename detected speaker IDs to real names.
- Export TXT, SRT, or JSON transcripts with speaker names applied.

Speaker Scribe cannot infer real human names from arbitrary audio by itself. It detects speaker identities such as `SPEAKER_00`, then lets the user label those identities.

## Stack

- Frontend: Vite, React, TypeScript, lucide-react.
- Backend: FastAPI, Pydantic, uvicorn.
- Speech stack: `whispermlx` optional extra, built on `mlx-whisper`, WhisperX alignment, and pyannote diarization.
- Runtime storage: local `data/` folder with uploaded audio and `jobs.json`.

## Requirements

- macOS on Apple Silicon for the intended MLX path.
- `ffmpeg` available on PATH for audio decoding in the speech stack.
- Python 3.13 for `whispermlx` today. The base app can run on Python 3.14, but the `ml` extra is pinned behind `python_version < '3.14'` because `whispermlx` currently declares that range.
- Hugging Face token with accepted pyannote model terms for diarization.

## Setup

```bash
pnpm install
uv sync --extra test
```

For real MLX transcription:

```bash
uv sync --extra ml --python 3.13
export HUGGINGFACE_TOKEN=...
```

For a deterministic smoke-test engine that does not download models:

```bash
export SPEAKER_SCRIBE_ENGINE=mock
```

## Run

Start the API:

```bash
uv run uvicorn speaker_scribe_backend.app:app --app-dir backend --host 127.0.0.1 --port 8118 --reload
```

Start the web app:

```bash
pnpm dev
```

Then open `http://127.0.0.1:5178`.

Or run both with:

```bash
./scripts/dev.sh
```

## Check

```bash
./scripts/check.sh
```

This runs frontend type/build/test checks plus backend unit tests.

## Open Source

This repository is MIT licensed. It depends on open-source projects with their own licenses, including `whispermlx` under BSD-2-Clause and pyannote tooling under MIT.
