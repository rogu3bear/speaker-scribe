"""What Whisper models exist, which are on disk, and how to add or remove them.

Weights are large and downloaded lazily on first use, which means a user can pick
a model and then wait several minutes with no idea why. This module makes the
local cache visible so the choice is informed, and lets a model be fetched ahead
of time or removed to reclaim space.

Every heavy import is deferred so the base install, which has no speech stack,
can still import and serve the API.
"""

from __future__ import annotations

import os
import shutil
import threading
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Literal

ModelState = Literal["available", "missing", "downloading", "error"]


@dataclass(frozen=True)
class CatalogEntry:
    """A model offered in the UI. `download_mb` is the published archive size."""

    value: str
    repo: str
    label: str
    download_mb: int
    speed: str
    hint: str


CATALOG: tuple[CatalogEntry, ...] = (
    CatalogEntry(
        value="tiny",
        repo="mlx-community/whisper-tiny-mlx",
        label="Tiny",
        download_mb=75,
        speed="fastest",
        hint="Roughest accuracy. Good for checking that a file processes at all.",
    ),
    CatalogEntry(
        value="base",
        repo="mlx-community/whisper-base-mlx",
        label="Base",
        download_mb=145,
        speed="very fast",
        hint="Still misses names and technical terms. Fine for a rough gist.",
    ),
    CatalogEntry(
        value="small",
        repo="mlx-community/whisper-small-mlx",
        label="Small",
        download_mb=480,
        speed="~60x realtime",
        hint="Usable for clear speech. Struggles with crosstalk and accents.",
    ),
    CatalogEntry(
        value="medium",
        repo="mlx-community/whisper-medium-mlx",
        label="Medium",
        download_mb=1500,
        speed="fast",
        hint="Close to large on clean audio, at half the download.",
    ),
    CatalogEntry(
        value="large-v3-turbo",
        repo="mlx-community/whisper-large-v3-turbo",
        label="Large v3 Turbo",
        download_mb=1600,
        speed="~4x faster than large-v3",
        hint="Near-large accuracy for far less time. Best default for interviews.",
    ),
    CatalogEntry(
        value="large-v3",
        repo="mlx-community/whisper-large-v3-mlx",
        label="Large v3",
        download_mb=3100,
        speed="~30x realtime",
        hint="Most accurate on accents, names and crosstalk. Slowest and largest.",
    ),
)

# Speaker embedding model. Listed so the cache view accounts for everything the
# app pulls down, but it is required for diarization and so is not removable.
EMBEDDING_REPO = "speechbrain/spkrec-ecapa-voxceleb"

# The packaged app ships some weights inside itself so that a first run works
# with no network. This names the directory they sit in; it is unset everywhere
# else, and seeding is then a no-op.
BUNDLED_MODELS_ENV = "SPEAKER_SCRIBE_BUNDLED_MODELS"


def bundled_models_dir() -> Path | None:
    """The read-only cache shipped inside the app, when there is one."""
    raw = os.getenv(BUNDLED_MODELS_ENV)
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_dir() else None


def _copy_into(source: Path, destination: Path) -> bool:
    """Copy one model directory across, or report that it could not be done.

    Staged under a temporary name and moved into place, so an interrupted copy
    cannot leave behind something that looks like a complete model.
    """
    if destination.exists():
        return False

    staging = destination.parent / f".{destination.name}.incoming"
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if staging.exists():
            shutil.rmtree(staging)
        # symlinks=True matters for the hub cache, which stores every file once
        # as a blob and links the snapshot at it. Resolving those would duplicate
        # the weights and roughly double the space the app occupies.
        shutil.copytree(source, staging, symlinks=True)
        staging.rename(destination)
    except OSError:
        shutil.rmtree(staging, ignore_errors=True)
        return False
    return True


def seed_bundled_models() -> list[str]:
    """Copy shipped weights into the real caches. Returns what was copied.

    The bundle is read-only and gets replaced wholesale on update, so it cannot
    be the cache itself: downloading a second model has to work, and a model the
    user deletes has to stay deleted. Copying once into the writable cache gives
    both, and makes a bundled model indistinguishable from a downloaded one
    everywhere else in this module.

    Two destinations, because the two kinds of weight are cached differently.
    Whisper models are Hugging Face repos and belong in the hub cache; the
    speaker embedding model is loaded by SpeechBrain from a plain directory.
    The bundle mirrors that split:

        models/hub/models--mlx-community--whisper-small-mlx
        models/speechbrain/spkrec-ecapa-voxceleb

    Only ever adds. An existing directory is left alone even if it is a partial
    download, because overwriting the live cache underneath a running app is a
    worse failure than a re-download the user can trigger themselves.
    """
    from .diarize import model_cache_dir

    source = bundled_models_dir()
    if source is None:
        return []

    seeded: list[str] = []

    hub_source = source / "hub"
    if hub_source.is_dir():
        try:
            from huggingface_hub.constants import HF_HUB_CACHE
        except ImportError:
            HF_HUB_CACHE = None  # noqa: N806 - mirrors the upstream constant name
        if HF_HUB_CACHE:
            hub_cache = Path(HF_HUB_CACHE)
            for entry in sorted(hub_source.glob("models--*")):
                if entry.is_dir() and _copy_into(entry, hub_cache / entry.name):
                    seeded.append(entry.name)

    speechbrain_source = source / "speechbrain"
    if speechbrain_source.is_dir():
        savedir = model_cache_dir()
        for entry in sorted(p for p in speechbrain_source.iterdir() if p.is_dir()):
            if _copy_into(entry, savedir / entry.name):
                seeded.append(f"speechbrain/{entry.name}")

    return seeded


@dataclass
class _Transfers:
    """In-flight downloads, keyed by model value."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    active: dict[str, str] = field(default_factory=dict)  # value -> "downloading" | error text

    def mark(self, value: str, state: str) -> None:
        with self.lock:
            self.active[value] = state

    def clear(self, value: str) -> None:
        with self.lock:
            self.active.pop(value, None)

    def snapshot(self) -> dict[str, str]:
        with self.lock:
            return dict(self.active)


TRANSFERS = _Transfers()


def entry_for(value: str) -> CatalogEntry | None:
    return next((item for item in CATALOG if item.value == value), None)


def cached_sizes() -> dict[str, int]:
    """Bytes on disk per repo id. Empty when the cache cannot be read."""
    try:
        from huggingface_hub import scan_cache_dir
    except ImportError:
        return {}

    try:
        info = scan_cache_dir()
    except Exception:  # noqa: BLE001 - a missing or unreadable cache is not an error here
        return {}

    return {
        repo.repo_id: repo.size_on_disk for repo in info.repos if repo.repo_type == "model"
    }


def download(value: str) -> None:
    """Fetch a model's weights. Blocking; callers run it on a worker thread."""
    entry = entry_for(value)
    if entry is None:
        raise ValueError(f"Unknown model {value!r}")

    TRANSFERS.mark(value, "downloading")
    try:
        # Imported inside the guard: on a base install this raises ImportError,
        # and outside it the model would sit on "downloading" forever with the
        # UI polling a state that can never change.
        from huggingface_hub import snapshot_download

        snapshot_download(entry.repo)
    except Exception as exc:  # noqa: BLE001 - surfaced to the UI as model state
        TRANSFERS.mark(value, f"error: {exc}")
        raise
    else:
        TRANSFERS.clear(value)


def remove(value: str) -> int:
    """Delete a model's cached weights. Returns bytes freed."""
    entry = entry_for(value)
    if entry is None:
        raise ValueError(f"Unknown model {value!r}")

    from huggingface_hub import scan_cache_dir

    info = scan_cache_dir()
    revisions = [
        revision.commit_hash
        for repo in info.repos
        if repo.repo_id == entry.repo and repo.repo_type == "model"
        for revision in repo.revisions
    ]
    if not revisions:
        return 0

    strategy = info.delete_revisions(*revisions)
    freed = strategy.expected_freed_size
    strategy.execute()
    TRANSFERS.clear(value)
    return freed
