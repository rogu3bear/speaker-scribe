import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from speaker_scribe_backend import app as app_module
from speaker_scribe_backend import catalog
from speaker_scribe_backend.app import AppSettings
from speaker_scribe_backend.store import JobStore

LARGE = "mlx-community/whisper-large-v3-mlx"


def client_over(tmp_path: Path) -> TestClient:
    app_module.app.state.settings = AppSettings(data_root=tmp_path, max_upload_mb=1)
    app_module.app.state.store = JobStore(tmp_path)
    return TestClient(app_module.app)


def by_value(body: list[dict]) -> dict[str, dict]:
    return {item["value"]: item for item in body}


def test_catalog_values_all_resolve_to_a_real_mlx_repo() -> None:
    """A catalog entry the engine cannot load would fail only at transcription."""
    from speaker_scribe_backend.pipeline import resolve_model

    for entry in catalog.CATALOG:
        assert resolve_model(entry.value) == entry.repo


def test_models_report_available_when_cached(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(catalog, "cached_sizes", lambda: {LARGE: 3_100_000_000})

    body = by_value(client_over(tmp_path).get("/api/models").json())

    assert body["large-v3"]["state"] == "available"
    assert body["large-v3"]["size_on_disk"] == 3_100_000_000


def test_models_report_missing_when_not_cached(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(catalog, "cached_sizes", lambda: {})

    body = by_value(client_over(tmp_path).get("/api/models").json())

    assert {item["state"] for item in body.values()} == {"missing"}
    assert body["tiny"]["size_on_disk"] == 0


def test_models_report_an_in_flight_download(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(catalog, "cached_sizes", lambda: {})
    catalog.TRANSFERS.mark("medium", "downloading")
    try:
        body = by_value(client_over(tmp_path).get("/api/models").json())
        assert body["medium"]["state"] == "downloading"
    finally:
        catalog.TRANSFERS.clear("medium")


def test_models_surface_a_failed_download(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(catalog, "cached_sizes", lambda: {})
    catalog.TRANSFERS.mark("base", "error: no route to host")
    try:
        body = by_value(client_over(tmp_path).get("/api/models").json())
        assert body["base"]["state"] == "error"
        assert body["base"]["detail"] == "no route to host"
    finally:
        catalog.TRANSFERS.clear("base")


def test_an_unreadable_cache_degrades_to_missing(monkeypatch, tmp_path: Path) -> None:
    """A broken cache must not take the whole API down."""
    pytest.importorskip("huggingface_hub")

    def explode() -> dict[str, int]:
        raise OSError("cache is on fire")

    monkeypatch.setattr("huggingface_hub.scan_cache_dir", explode)

    assert catalog.cached_sizes() == {}


def test_cached_sizes_is_empty_without_the_speech_stack(monkeypatch) -> None:
    """The base install has no huggingface_hub; the catalog still has to answer."""
    monkeypatch.setitem(sys.modules, "huggingface_hub", None)

    assert catalog.cached_sizes() == {}


def test_a_download_that_cannot_start_reports_an_error_not_a_stuck_spinner(
    monkeypatch, tmp_path: Path
) -> None:
    """A transfer left on "downloading" makes the UI poll a state that never changes."""
    monkeypatch.setattr(catalog, "cached_sizes", lambda: {})
    monkeypatch.setitem(sys.modules, "huggingface_hub", None)

    try:
        with pytest.raises(Exception):
            catalog.download("base")
        assert catalog.TRANSFERS.snapshot()["base"].startswith("error:")
    finally:
        catalog.TRANSFERS.clear("base")


def test_downloading_an_unknown_model_is_a_404(tmp_path: Path) -> None:
    assert client_over(tmp_path).post("/api/models/nope/download").status_code == 404


def test_removing_an_unknown_model_is_a_404(tmp_path: Path) -> None:
    assert client_over(tmp_path).delete("/api/models/nope").status_code == 404


def test_download_returns_immediately_and_marks_the_model(monkeypatch, tmp_path: Path) -> None:
    """The fetch runs on a thread; the request must not block on gigabytes."""
    monkeypatch.setattr(catalog, "cached_sizes", lambda: {})
    monkeypatch.setattr(catalog, "download", lambda value: None)

    body = by_value(client_over(tmp_path).post("/api/models/medium/download").json())

    assert body["medium"]["state"] in {"downloading", "missing"}
    catalog.TRANSFERS.clear("medium")


def test_remove_reports_a_failure_rather_than_a_bare_500(monkeypatch, tmp_path: Path) -> None:
    def explode(value: str) -> int:
        raise OSError("read-only file system")

    monkeypatch.setattr(catalog, "remove", explode)

    response = client_over(tmp_path).delete("/api/models/small")

    assert response.status_code == 500
    assert "read-only file system" in response.json()["detail"]
