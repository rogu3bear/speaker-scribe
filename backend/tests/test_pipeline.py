import importlib.util
from pathlib import Path

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
