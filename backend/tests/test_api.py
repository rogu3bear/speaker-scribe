from pathlib import Path

from fastapi.testclient import TestClient

from speaker_scribe_backend import app as app_module


def test_health_reports_mock_engine(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SPEAKER_SCRIBE_ENGINE", "mock")
    monkeypatch.setattr(app_module, "DATA_ROOT", tmp_path)

    client = TestClient(app_module.app)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["ml_ready"] is True
