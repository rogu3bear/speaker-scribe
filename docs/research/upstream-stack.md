# Upstream Stack Notes

Checked June 23, 2026.

## Selected Stack

- `KalebJS/whispermlx`: open-source WhisperX fork for Apple Silicon that replaces the inference backend with `mlx-whisper`, while retaining word-level timestamps, VAD, and speaker diarization.
- `mlx-whisper`: MLX Whisper package for speech transcription on Apple Silicon.
- `pyannote.audio`: open-source Python toolkit for speaker diarization.

## Operational Notes

- `whispermlx` exposes both CLI and Python APIs. Its README shows diarization via `DiarizationPipeline(token="YOUR_HF_TOKEN")` and `assign_word_speakers`.
- pyannote diarization models require accepting model terms and using a Hugging Face token.
- The app keeps `whispermlx` in the optional `ml` extra so tests and UI work do not force model/runtime downloads.

## Sources

- https://github.com/KalebJS/whispermlx
- https://pypi.org/project/mlx-whisper/
- https://github.com/pyannote/pyannote-audio
- https://huggingface.co/pyannote/speaker-diarization-3.1
- https://mlx-framework.org/
