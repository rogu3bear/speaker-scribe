from __future__ import annotations

import importlib.util
import os
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .diarize import LocalDiarizer
from .diarize import assign_speakers
from .models import Speaker
from .models import TranscribeOptions
from .models import TranscriptSegment
from .transcript import build_speakers
from .transcript import normalize_transcription_result

ProgressCallback = Callable[[float, str], None]

# mlx-whisper loads weights by Hugging Face repo id, so the short names the UI
# offers are mapped onto their MLX conversions. Anything else is passed through,
# which lets a user paste any mlx-community repo id.
MLX_MODEL_ALIASES = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
}

# Everything the real engine needs, checked without importing the heavy modules.
REQUIRED_MODULES = [
    ("mlx_whisper", "mlx-whisper"),
    ("silero_vad", "silero-vad"),
    ("speechbrain", "speechbrain"),
    ("sklearn", "scikit-learn"),
]


@dataclass(frozen=True)
class TranscriptionResult:
    segments: list[TranscriptSegment]
    duration: float | None
    language: str | None = None

    @property
    def speakers(self) -> list[Speaker]:
        return build_speakers(self.segments)


class Transcriber(Protocol):
    def transcribe(
        self,
        audio_path: Path,
        options: TranscribeOptions,
        progress: ProgressCallback,
    ) -> TranscriptionResult:
        ...


def resolve_model(model: str) -> str:
    return MLX_MODEL_ALIASES.get(model, model)


class MlxWhisperTranscriber:
    """MLX Whisper transcription plus local, account-free diarization."""

    def transcribe(
        self,
        audio_path: Path,
        options: TranscribeOptions,
        progress: ProgressCallback,
    ) -> TranscriptionResult:
        try:
            import mlx_whisper
        except ImportError as exc:
            raise RuntimeError(
                "mlx-whisper is not installed. Run `uv sync --extra ml` on Apple Silicon "
                "before starting real transcription."
            ) from exc

        if shutil.which("ffmpeg") is None:
            raise RuntimeError(
                "ffmpeg was not found on PATH. Install it with `brew install ffmpeg` "
                "before starting real transcription."
            )

        progress(0.1, "Loading MLX Whisper model")
        transcribe_kwargs: dict[str, object] = {"word_timestamps": True}
        if options.language:
            transcribe_kwargs["language"] = options.language

        progress(0.18, "Transcribing audio with MLX Whisper")
        result = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo=resolve_model(options.model),
            **transcribe_kwargs,
        )
        language = str(result.get("language") or options.language or "") or None

        if options.diarize:
            progress(0.5, "Preparing audio for speaker analysis")
            turns = LocalDiarizer().diarize(audio_path, options, progress)
            result = assign_speakers(result, turns)

        progress(0.9, "Normalizing transcript segments")
        segments, duration = normalize_transcription_result(result)
        return TranscriptionResult(segments=segments, duration=duration, language=language)


class MockTranscriber:
    """Deterministic engine for local smoke tests and UI demos."""

    def transcribe(
        self,
        audio_path: Path,
        options: TranscribeOptions,
        progress: ProgressCallback,
    ) -> TranscriptionResult:
        del audio_path
        for value, stage in [
            (0.2, "Reading audio headers"),
            (0.48, "Generating transcript"),
            (0.74, "Estimating speaker turns"),
            (0.92, "Preparing export formats"),
        ]:
            progress(value, stage)
            time.sleep(0.02)

        segments = [
            TranscriptSegment(
                id="seg-1",
                start=0.0,
                end=4.8,
                speaker="SPEAKER_00",
                text="This mock transcript proves the upload pipeline without downloading a model.",
            ),
            TranscriptSegment(
                id="seg-2",
                start=5.1,
                end=9.6,
                speaker="SPEAKER_01" if options.diarize else "SPEAKER_00",
                text="Install the ML extra to run MLX Whisper and local diarization on real audio.",
            ),
        ]
        return TranscriptionResult(segments=segments, duration=9.6, language=options.language or "en")


def engine_name() -> str:
    return os.getenv("SPEAKER_SCRIBE_ENGINE", "mlx").lower()


def create_transcriber() -> Transcriber:
    if engine_name() == "mock":
        return MockTranscriber()
    return MlxWhisperTranscriber()


def ml_ready() -> tuple[bool, str | None]:
    """Report whether a real run can start, and what is missing if it cannot."""
    if engine_name() == "mock":
        return True, "mock engine selected"

    missing = [
        name for module, name in REQUIRED_MODULES if importlib.util.find_spec(module) is None
    ]
    if missing:
        return False, f"missing packages: {', '.join(missing)} — run `uv sync --extra ml`"
    if shutil.which("ffmpeg") is None:
        return False, "ffmpeg not found on PATH — run `brew install ffmpeg`"
    return True, None
