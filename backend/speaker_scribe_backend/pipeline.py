from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import threading
import time
from collections.abc import Callable
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from typing import Protocol

from .diarize import LocalDiarizer
from .diarize import assign_speakers
from .diarize import ffmpeg_path
from .models import Speaker
from .models import TranscribeOptions
from .models import TranscriptSegment
from .transcript import build_speakers
from .transcript import normalize_transcription_result

ProgressCallback = Callable[[float, str], None]

# Transcription dominates wall clock — roughly 70s of an 84s run on a 15-minute
# recording — so it owns most of the bar. Diarization reports its own progress
# across the remainder. Without diarization transcription runs to the end.
TRANSCRIBE_PROGRESS_START = 0.05
TRANSCRIBE_PROGRESS_END_WITH_DIARIZATION = 0.78
TRANSCRIBE_PROGRESS_END = 0.95
TRANSCRIBING_STAGE = "Transcribing audio with MLX Whisper"

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


# Which job's progress the running thread is reporting. Jobs run one per thread,
# so the sink has to be thread-local: a shared one would cross wires between two
# uploads processing at the same time.
_SINK = threading.local()


class FrameProgressBar:
    """Stands in for mlx-whisper's internal tqdm bar and forwards its updates.

    mlx-whisper exposes no progress callback, but it drives a tqdm bar over audio
    frames and looks it up as a module attribute at call time. Standing in for
    that attribute is the only way to see inside the single long call that
    dominates a job, which otherwise leaves the UI frozen for minutes.
    """

    def __init__(self, sink: tuple[ProgressCallback, float, float] | None, total: int) -> None:
        self._sink = sink
        self._total = total
        self._done = 0

    def __enter__(self) -> "FrameProgressBar":
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False

    def update(self, amount: int = 1) -> None:
        self._done += amount
        if self._sink is None or self._total <= 0:
            return
        report, start, end = self._sink
        fraction = min(1.0, max(0.0, self._done / self._total))
        report(start + (end - start) * fraction, TRANSCRIBING_STAGE)

    def close(self) -> None:
        return None


def _new_frame_bar(*_args: Any, total: int | None = None, **_kwargs: Any) -> FrameProgressBar:
    """Build a bar bound to the calling thread's job. One per transcription."""
    return FrameProgressBar(getattr(_SINK, "target", None), total or 0)


def _install_frame_bar() -> bool:
    """Put the stand-in in place once. Never restored, so it cannot be inverted.

    Save-and-restore around each call looked natural and was wrong: with two jobs
    in flight the second captures the first's stand-in as the "original" and puts
    it back on exit, leaving the module permanently pointed at a finished job's
    callback. Installing once and routing through a thread-local removes the
    restore step that made that possible.
    """
    try:
        import mlx_whisper  # noqa: F401
    except ImportError:
        return False

    # Must come from sys.modules: mlx_whisper/__init__.py rebinds the name
    # `transcribe` to the function, so `mlx_whisper.transcribe` is not the module.
    module = sys.modules.get("mlx_whisper.transcribe")
    existing = getattr(module, "tqdm", None) if module is not None else None
    if existing is None:
        return False
    if getattr(existing, "speaker_scribe_bar", False):
        return True

    module.tqdm = SimpleNamespace(tqdm=_new_frame_bar, speaker_scribe_bar=True)
    return True


@contextmanager
def frame_progress(report: ProgressCallback, start: float, end: float) -> Iterator[None]:
    """Route mlx-whisper's frame counter into `report` for the duration of a call.

    Degrades to no progress updates rather than failing the job if the internals
    ever move; transcription itself is unaffected either way.
    """
    if not _install_frame_bar():
        yield
        return

    previous = getattr(_SINK, "target", None)
    _SINK.target = (report, start, end)
    try:
        yield
    finally:
        _SINK.target = previous


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

        if ffmpeg_path() is None:
            raise RuntimeError(
                "ffmpeg was not found. Install it with `brew install ffmpeg`, or set "
                "SPEAKER_SCRIBE_FFMPEG to a binary, before starting real transcription."
            )

        progress(0.03, "Loading MLX Whisper model")
        # verbose=False is what enables mlx-whisper's frame counter; None disables it.
        transcribe_kwargs: dict[str, object] = {"word_timestamps": True, "verbose": False}
        if options.language:
            transcribe_kwargs["language"] = options.language

        transcribe_end = (
            TRANSCRIBE_PROGRESS_END_WITH_DIARIZATION if options.diarize else TRANSCRIBE_PROGRESS_END
        )
        progress(TRANSCRIBE_PROGRESS_START, TRANSCRIBING_STAGE)
        with frame_progress(progress, TRANSCRIBE_PROGRESS_START, transcribe_end):
            result = mlx_whisper.transcribe(
                str(audio_path),
                path_or_hf_repo=resolve_model(options.model),
                **transcribe_kwargs,
            )
        language = str(result.get("language") or options.language or "") or None

        if options.diarize:
            turns = LocalDiarizer().diarize(audio_path, options, progress)
            result = assign_speakers(result, turns)

        progress(0.97, "Normalizing transcript segments")
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
    if ffmpeg_path() is None:
        return False, "ffmpeg not found — run `brew install ffmpeg`"
    return True, None
