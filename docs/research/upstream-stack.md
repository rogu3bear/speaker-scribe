# Upstream Stack Notes

Stack selected June 23, 2026. Replaced the gated diarization path July 27, 2026.

## Selected Stack

- `mlx-whisper`: MLX Whisper package for speech transcription on Apple Silicon. Emits
  word-level timestamps directly, so no separate forced-alignment model is needed.
- `silero-vad`: MIT-licensed voice activity detector. The pip package ships its own
  weights, so speech detection needs no download and no account.
- `speechbrain`: provides the `spkrec-ecapa-voxceleb` speaker embedding model, fetched
  once from a public Hugging Face repo that requires no terms acceptance and no token.
- `scikit-learn`: agglomerative clustering plus silhouette scoring to group embeddings
  into speakers and choose the speaker count.

## Why The Diarization Path Changed

The original design used `KalebJS/whispermlx` (a WhisperX fork) with pyannote
diarization. That path required a Hugging Face token and acceptance of the pyannote
model terms, which put real diarization behind an account. It also pulled the entire
pyannote, lightning, torchvision and transformers tree in as a transitive dependency.

The current path keeps MLX Whisper transcription and replaces only the diarization
stage, so speaker turns are produced with no credential of any kind.

## Operational Notes

- `mlx-whisper` loads weights by Hugging Face repo id, so the UI's short model names are
  mapped to `mlx-community/*` repos in `pipeline.MLX_MODEL_ALIASES`.
- `ffmpeg` is required on PATH to decode source audio to 16 kHz mono PCM.
- Speaker count is chosen by silhouette score over candidate cluster counts, with an
  absolute cosine-distance floor so a single-speaker recording is not split.
- `mlx-whisper` leaves `numba` unpinned; without a floor the resolver keeps the newest
  numpy and backtracks numba to 0.53.1, whose llvmlite cannot build on Python >= 3.10.

## Sources

- https://pypi.org/project/mlx-whisper/
- https://github.com/snakers4/silero-vad
- https://speechbrain.github.io/
- https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb
- https://scikit-learn.org/stable/modules/clustering.html
- https://mlx-framework.org/
