import importlib.util
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from speaker_scribe_backend import app as app_module
from speaker_scribe_backend import pipeline
from speaker_scribe_backend.app import AppSettings
from speaker_scribe_backend.pipeline import MlxWhisperTranscriber
from speaker_scribe_backend.pipeline import MockTranscriber
from speaker_scribe_backend.pipeline import create_transcriber
from speaker_scribe_backend.pipeline import ml_ready
from speaker_scribe_backend.store import JobStore

real_find_spec = importlib.util.find_spec


def hide_module(monkeypatch, hidden: str) -> None:
    def fake_find_spec(name: str, *args, **kwargs):
        return None if name == hidden else real_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(pipeline.importlib.util, "find_spec", fake_find_spec)


def test_frame_progress_bar_maps_frame_counts_onto_its_span() -> None:
    seen: list[tuple[float, str]] = []
    bar = pipeline.FrameProgressBar((lambda value, stage: seen.append((value, stage)), 0.2, 0.8), 100)

    with bar as active:
        active.update(25)
        active.update(25)
        active.update(50)

    assert [round(value, 3) for value, _ in seen] == [0.35, 0.5, 0.8]
    assert {stage for _, stage in seen} == {pipeline.TRANSCRIBING_STAGE}


def test_frame_progress_bar_never_exceeds_its_span() -> None:
    seen: list[float] = []
    bar = pipeline.FrameProgressBar((lambda value, _stage: seen.append(value), 0.0, 0.5), 10)

    bar.update(999)

    assert seen == [0.5]


def test_frame_progress_bar_ignores_an_unknown_total() -> None:
    """mlx-whisper always passes a total, but a silent divide-by-zero would be worse."""
    seen: list[float] = []
    pipeline.FrameProgressBar((lambda value, _stage: seen.append(value), 0.0, 1.0), 0).update(5)

    assert seen == []


def test_frame_progress_bar_without_a_sink_is_inert() -> None:
    """A bar built outside any job must not report anywhere."""
    pipeline.FrameProgressBar(None, 100).update(50)


def test_frame_progress_clears_its_sink_even_if_the_body_raises() -> None:
    pytest.importorskip("mlx_whisper.transcribe")

    with pytest.raises(RuntimeError):
        with pipeline.frame_progress(lambda _value, _stage: None, 0.0, 1.0):
            raise RuntimeError("transcription blew up")

    assert getattr(pipeline._SINK, "target", None) is None


def test_concurrent_jobs_keep_their_progress_apart() -> None:
    """Two uploads transcribe at once; neither may report into the other's job.

    An earlier version saved and restored the patched module attribute per call.
    With overlapping jobs the second captured the first's stand-in as the
    "original" and put it back, leaving every later transcription reporting into
    a finished job -- which rewrote that job's stored row back to "running".
    """
    pytest.importorskip("mlx_whisper.transcribe")

    seen: dict[str, list[float]] = {"a": [], "b": []}
    started = threading.Barrier(2)

    def run(name: str, start: float, end: float) -> None:
        with pipeline.frame_progress(
            lambda value, _stage: seen[name].append(value), start, end
        ):
            started.wait(timeout=5)  # guarantee the two jobs overlap
            bar = pipeline._new_frame_bar(total=10)
            for _ in range(10):
                bar.update(1)

    threads = [
        threading.Thread(target=run, args=("a", 0.0, 0.5)),
        threading.Thread(target=run, args=("b", 0.5, 1.0)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    # Each job's values stay strictly inside its own span.
    assert seen["a"] and all(0.0 <= value <= 0.5 for value in seen["a"])
    assert seen["b"] and all(0.5 <= value <= 1.0 for value in seen["b"])
    assert seen["a"] == sorted(seen["a"])
    assert seen["b"] == sorted(seen["b"])


def test_a_finished_job_stops_receiving_progress() -> None:
    """The corruption this guards: a later job writing into a completed one."""
    pytest.importorskip("mlx_whisper.transcribe")

    finished: list[float] = []
    with pipeline.frame_progress(lambda value, _stage: finished.append(value), 0.0, 0.5):
        pipeline._new_frame_bar(total=10).update(5)
    during = len(finished)

    with pipeline.frame_progress(lambda _value, _stage: None, 0.5, 1.0):
        pipeline._new_frame_bar(total=10).update(5)

    assert len(finished) == during


def test_frame_progress_is_a_no_op_without_the_engine(monkeypatch) -> None:
    """Progress reporting must never be the thing that fails a job."""
    monkeypatch.setitem(__import__("sys").modules, "mlx_whisper.transcribe", None)

    with pipeline.frame_progress(lambda _value, _stage: None, 0.0, 1.0):
        pass


def test_mock_engine_is_always_ready(monkeypatch) -> None:
    monkeypatch.setenv("SPEAKER_SCRIBE_ENGINE", "mock")

    assert ml_ready() == (True, "mock engine selected")
    assert isinstance(create_transcriber(), MockTranscriber)


def test_real_engine_is_selected_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SPEAKER_SCRIBE_ENGINE", raising=False)

    assert isinstance(create_transcriber(), MlxWhisperTranscriber)


def test_ml_ready_names_the_missing_package(monkeypatch) -> None:
    monkeypatch.setenv("SPEAKER_SCRIBE_ENGINE", "mlx")
    hide_module(monkeypatch, "speechbrain")

    ready, detail = ml_ready()

    assert ready is False
    assert detail is not None
    assert "speechbrain" in detail
    assert "uv sync --extra ml" in detail


def test_ml_ready_reports_missing_ffmpeg(monkeypatch) -> None:
    """ffmpeg is only reported once the Python packages are all present."""
    monkeypatch.setenv("SPEAKER_SCRIBE_ENGINE", "mlx")
    monkeypatch.setattr(pipeline.importlib.util, "find_spec", lambda name, *a, **k: object())
    monkeypatch.setattr(pipeline.shutil, "which", lambda _: None)

    ready, detail = ml_ready()

    assert ready is False
    assert detail is not None
    assert "ffmpeg" in detail


def test_health_surfaces_the_reason_the_ui_warning_shows(monkeypatch, tmp_path: Path) -> None:
    """The upload panel renders health.detail, so it has to reach the API."""
    monkeypatch.setenv("SPEAKER_SCRIBE_ENGINE", "mlx")
    hide_module(monkeypatch, "mlx_whisper")
    app_module.app.state.settings = AppSettings(data_root=tmp_path, max_upload_mb=1)
    app_module.app.state.store = JobStore(tmp_path)

    body = TestClient(app_module.app).get("/api/health").json()

    assert body["ml_ready"] is False
    assert "mlx-whisper" in body["detail"]


def test_real_transcriber_reports_a_missing_engine_instead_of_crashing(monkeypatch) -> None:
    monkeypatch.setattr(pipeline.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setitem(__import__("sys").modules, "mlx_whisper", None)

    # Importing a module set to None raises ImportError, which the engine converts
    # into an actionable message rather than a bare traceback.
    try:
        MlxWhisperTranscriber().transcribe(
            Path("missing.wav"),
            pipeline.TranscribeOptions(model="large-v3", diarize=False),
            lambda value, stage: None,
        )
    except RuntimeError as error:
        assert "mlx-whisper is not installed" in str(error)
    else:  # pragma: no cover - only reached if the guard regresses
        raise AssertionError("expected a RuntimeError about the missing engine")
