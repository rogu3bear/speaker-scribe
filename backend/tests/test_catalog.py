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


# --- Weights shipped inside the packaged app -------------------------------
#
# The bundle is read-only and is replaced wholesale on update, so it cannot be
# the cache itself. These cover the copy out of it, which is the only reason a
# freshly installed app can transcribe without reaching the network.


def bundle_with(root: Path, *, hub: str | None = None, speechbrain: str | None = None) -> Path:
    """Build the directory layout the app ships, with placeholder weights."""
    source = root / "bundled"
    if hub is not None:
        blobs = source / "hub" / hub / "blobs"
        blobs.mkdir(parents=True)
        (blobs / "abc123").write_bytes(b"weights")
        snapshot = source / "hub" / hub / "snapshots" / "deadbeef"
        snapshot.mkdir(parents=True)
        # The hub stores each file once and links the snapshot at the blob.
        (snapshot / "weights.safetensors").symlink_to("../../blobs/abc123")
    if speechbrain is not None:
        saved = source / "speechbrain" / speechbrain
        saved.mkdir(parents=True)
        (saved / "hyperparams.yaml").write_text("placeholder")
    return source


def test_seeding_does_nothing_when_the_app_ships_no_weights(monkeypatch) -> None:
    monkeypatch.delenv(catalog.BUNDLED_MODELS_ENV, raising=False)

    assert catalog.seed_bundled_models() == []


def test_seeding_ignores_a_bundle_path_that_is_not_there(monkeypatch, tmp_path: Path) -> None:
    """A stale environment variable must not stop the server starting."""
    monkeypatch.setenv(catalog.BUNDLED_MODELS_ENV, str(tmp_path / "gone"))

    assert catalog.seed_bundled_models() == []


def test_seeding_copies_the_embedding_model_where_speechbrain_looks(
    monkeypatch, tmp_path: Path
) -> None:
    source = bundle_with(tmp_path, speechbrain="spkrec-ecapa-voxceleb")
    monkeypatch.setenv(catalog.BUNDLED_MODELS_ENV, str(source))
    monkeypatch.setenv("SPEAKER_SCRIBE_MODEL_CACHE", str(tmp_path / "cache"))

    seeded = catalog.seed_bundled_models()

    assert seeded == ["speechbrain/spkrec-ecapa-voxceleb"]
    assert (tmp_path / "cache" / "spkrec-ecapa-voxceleb" / "hyperparams.yaml").is_file()


def test_seeding_leaves_an_existing_model_untouched(monkeypatch, tmp_path: Path) -> None:
    """Seeding runs on every start; it must not overwrite what is already there."""
    source = bundle_with(tmp_path, speechbrain="spkrec-ecapa-voxceleb")
    monkeypatch.setenv(catalog.BUNDLED_MODELS_ENV, str(source))
    monkeypatch.setenv("SPEAKER_SCRIBE_MODEL_CACHE", str(tmp_path / "cache"))
    existing = tmp_path / "cache" / "spkrec-ecapa-voxceleb"
    existing.mkdir(parents=True)
    (existing / "hyperparams.yaml").write_text("the user's own copy")

    assert catalog.seed_bundled_models() == []
    assert (existing / "hyperparams.yaml").read_text() == "the user's own copy"


def test_seeding_copies_a_whisper_model_into_the_hub_cache(monkeypatch, tmp_path: Path) -> None:
    constants = pytest.importorskip("huggingface_hub.constants")
    name = "models--mlx-community--whisper-small-mlx"
    source = bundle_with(tmp_path, hub=name)
    monkeypatch.setenv(catalog.BUNDLED_MODELS_ENV, str(source))
    monkeypatch.setattr(constants, "HF_HUB_CACHE", str(tmp_path / "hub"))

    seeded = catalog.seed_bundled_models()

    assert seeded == [name]
    assert (tmp_path / "hub" / name / "blobs" / "abc123").read_bytes() == b"weights"


def test_seeding_keeps_the_hub_symlinks_rather_than_duplicating_weights(
    monkeypatch, tmp_path: Path
) -> None:
    """Resolving them would store every model twice and double the app's size."""
    constants = pytest.importorskip("huggingface_hub.constants")
    name = "models--mlx-community--whisper-small-mlx"
    source = bundle_with(tmp_path, hub=name)
    monkeypatch.setenv(catalog.BUNDLED_MODELS_ENV, str(source))
    monkeypatch.setattr(constants, "HF_HUB_CACHE", str(tmp_path / "hub"))

    catalog.seed_bundled_models()

    copied = tmp_path / "hub" / name / "snapshots" / "deadbeef" / "weights.safetensors"
    assert copied.is_symlink()
    assert copied.read_bytes() == b"weights"


def test_seeding_reports_both_kinds_of_weight(monkeypatch, tmp_path: Path) -> None:
    constants = pytest.importorskip("huggingface_hub.constants")
    name = "models--mlx-community--whisper-small-mlx"
    source = bundle_with(tmp_path, hub=name, speechbrain="spkrec-ecapa-voxceleb")
    monkeypatch.setenv(catalog.BUNDLED_MODELS_ENV, str(source))
    monkeypatch.setenv("SPEAKER_SCRIBE_MODEL_CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(constants, "HF_HUB_CACHE", str(tmp_path / "hub"))

    assert catalog.seed_bundled_models() == [name, "speechbrain/spkrec-ecapa-voxceleb"]


def test_a_failed_copy_leaves_no_half_written_model(monkeypatch, tmp_path: Path) -> None:
    """A partial copy that looked complete would resurface later as a bad model."""
    source = bundle_with(tmp_path, speechbrain="spkrec-ecapa-voxceleb")
    monkeypatch.setenv(catalog.BUNDLED_MODELS_ENV, str(source))
    monkeypatch.setenv("SPEAKER_SCRIBE_MODEL_CACHE", str(tmp_path / "cache"))

    def fail(*args, **kwargs):
        (tmp_path / "cache" / ".spkrec-ecapa-voxceleb.incoming").mkdir(parents=True)
        raise OSError("no space left on device")

    monkeypatch.setattr(catalog.shutil, "copytree", fail)

    assert catalog.seed_bundled_models() == []
    assert list((tmp_path / "cache").iterdir()) == []
