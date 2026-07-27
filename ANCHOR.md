# Anchor

## Product Truth

Speaker Scribe detects speaker identities, not real-world names. Real names come from user labeling or future enrolled voice profiles.

## Privacy Truth

Speaker embeddings are voice prints, and voice prints are biometric data. This holds
even though every byte stays on the user's machine.

- A voice profile stores embeddings and a user-chosen name. It never stores audio.
- Profiles live under the local `data/` tree and are never transmitted anywhere.
- A profile is created only by an explicit user action on a completed job. Running a
  transcript never enrolls anyone.
- Every profile is individually deletable, and deleting one removes its stored vectors.
- Speaker Scribe never identifies unknown speakers. It matches only against profiles the
  user deliberately enrolled, and it has no notion of a shared or global voice database.

The last point is a boundary, not a roadmap gap. Identifying strangers from audio is a
different product and is out of scope.

## Architecture Truth

- React/Vite owns the editor UI.
- FastAPI owns uploads, jobs, local storage, and exports.
- `mlx-whisper` transcribes; diarization is Silero VAD, SpeechBrain ECAPA embeddings, and clustering.
- Every speech model is loaded lazily so the app can build and test without downloading models.
- Diarization runs entirely on-machine and requires no account, token, or hosted service.
- `SPEAKER_SCRIBE_ENGINE=mock` is the sanctioned local smoke lane.

## Proof Truth

Passing frontend build/tests plus backend unit tests proves source health. Real transcription quality requires an Apple Silicon ML run with the `ml` extra, `ffmpeg`, and first-run model downloads.
