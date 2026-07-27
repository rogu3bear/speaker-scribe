"""What Whisper models exist, which are on disk, and how to add or remove them.

Weights are large and downloaded lazily on first use, which means a user can pick
a model and then wait several minutes with no idea why. This module makes the
local cache visible so the choice is informed, and lets a model be fetched ahead
of time or removed to reclaim space.

Every heavy import is deferred so the base install, which has no speech stack,
can still import and serve the API.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from dataclasses import field
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

    from huggingface_hub import snapshot_download

    TRANSFERS.mark(value, "downloading")
    try:
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
