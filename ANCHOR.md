# Anchor

## Product Truth

Speaker Scribe detects speaker identities, not real-world names. Real names come from user labeling or future enrolled voice profiles.

## Architecture Truth

- React/Vite owns the editor UI.
- FastAPI owns uploads, jobs, local storage, and exports.
- `mlx-whisper` transcribes; diarization is Silero VAD, SpeechBrain ECAPA embeddings, and clustering.
- Every speech model is loaded lazily so the app can build and test without downloading models.
- Diarization runs entirely on-machine and requires no account, token, or hosted service.
- `SPEAKER_SCRIBE_ENGINE=mock` is the sanctioned local smoke lane.

## Proof Truth

Passing frontend build/tests plus backend unit tests proves source health. Real transcription quality requires an Apple Silicon ML run with the `ml` extra, `ffmpeg`, and first-run model downloads.
