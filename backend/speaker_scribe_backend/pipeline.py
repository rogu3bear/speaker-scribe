from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .models import Speaker
from .models import TranscribeOptions
from .models import TranscriptSegment
from .transcript import build_speakers
from .transcript import normalize_whispermlx_result

ProgressCallback = Callable[[float, str], None]


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


class WhisperMlxTranscriber:
    def transcribe(
        self,
        audio_path: Path,
        options: TranscribeOptions,
        progress: ProgressCallback,
    ) -> TranscriptionResult:
        try:
            import whispermlx
        except ImportError as exc:
            raise RuntimeError(
                "whispermlx is not installed. Run `uv sync --extra ml --python 3.13` "
                "on Apple Silicon before starting real transcription."
            ) from exc

        progress(0.08, "Loading MLX Whisper model")
        model = whispermlx.load_model(options.model, device="cpu")

        progress(0.18, "Transcribing audio with MLX Whisper")
        transcribe_kwargs: dict[str, str] = {}
        if options.language:
            transcribe_kwargs["language"] = options.language
        result = model.transcribe(str(audio_path), **transcribe_kwargs)

        if options.diarize:
            token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
            if not token:
                raise RuntimeError(
                    "Speaker diarization requires HUGGINGFACE_TOKEN or HF_TOKEN with access "
                    "to the pyannote diarization model."
                )

            language = str(result.get("language") or options.language or "en")
            progress(0.52, "Aligning words for speaker attribution")
            model_a, metadata = whispermlx.load_align_model(language_code=language, device="cpu")
            result = whispermlx.align(result["segments"], model_a, metadata, str(audio_path), device="cpu")

            progress(0.72, "Detecting speaker turns with pyannote")
            from whispermlx.diarize import DiarizationPipeline

            diarize_model = DiarizationPipeline(token=token, device="cpu")
            diarize_kwargs: dict[str, int] = {}
            if options.min_speakers is not None:
                diarize_kwargs["min_speakers"] = options.min_speakers
            if options.max_speakers is not None:
                diarize_kwargs["max_speakers"] = options.max_speakers

            diarize_segments = diarize_model(str(audio_path), **diarize_kwargs)
            result = whispermlx.assign_word_speakers(diarize_segments, result)

        progress(0.9, "Normalizing transcript segments")
        segments, duration = normalize_whispermlx_result(result)
        return TranscriptionResult(
            segments=segments,
            duration=duration,
            language=str(result.get("language") or options.language or "") or None,
        )


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
                text="Install the ML extra to run whispermlx and pyannote on real audio.",
            ),
        ]
        return TranscriptionResult(segments=segments, duration=9.6, language=options.language or "en")


def create_transcriber() -> Transcriber:
    if os.getenv("SPEAKER_SCRIBE_ENGINE", "mlx").lower() == "mock":
        return MockTranscriber()
    return WhisperMlxTranscriber()


def ml_ready() -> tuple[bool, str | None]:
    if os.getenv("SPEAKER_SCRIBE_ENGINE", "mlx").lower() == "mock":
        return True, "mock engine selected"
    try:
        import whispermlx  # noqa: F401
    except ImportError:
        return False, "whispermlx not installed"
    return True, None
