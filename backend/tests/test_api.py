import time
from pathlib import Path

from fastapi.testclient import TestClient

from speaker_scribe_backend import app as app_module
from speaker_scribe_backend.app import AppSettings
from speaker_scribe_backend.store import JobStore


def configure_test_app(monkeypatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("SPEAKER_SCRIBE_ENGINE", "mock")
    app_module.app.state.settings = AppSettings(data_root=tmp_path, max_upload_mb=1)
    app_module.app.state.store = JobStore(tmp_path)
    return TestClient(app_module.app)


def test_health_reports_mock_engine(monkeypatch, tmp_path: Path) -> None:
    client = configure_test_app(monkeypatch, tmp_path)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["ml_ready"] is True


def test_upload_audio_completes_with_mock_engine(monkeypatch, tmp_path: Path) -> None:
    client = configure_test_app(monkeypatch, tmp_path)

    response = client.post(
        "/api/jobs",
        data={"model": "large-v3", "diarize": "true"},
        files={"file": ("sample.wav", b"fake audio", "audio/wav")},
    )

    assert response.status_code == 200
    job_id = response.json()["id"]

    job = None
    for _ in range(20):
        job_response = client.get(f"/api/jobs/{job_id}")
        assert job_response.status_code == 200
        job = job_response.json()
        if job["status"] == "completed":
            break
        time.sleep(0.05)

    assert job is not None
    assert job["status"] == "completed"
    assert len(job["speakers"]) == 2
    assert "mock transcript" in job["segments"][0]["text"]
