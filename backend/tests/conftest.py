import json
from collections.abc import Callable
from pathlib import Path

import pytest

JobWriter = Callable[..., None]


@pytest.fixture
def write_jobs() -> JobWriter:
    """Seed a store's jobs.json directly, bypassing the API.

    Lets a test start from a store state the API cannot easily produce, such as
    a job left running by a killed process or a row with a legacy timestamp.
    """

    def write(
        root: Path,
        created_at: list[str],
        statuses: list[str] | None = None,
        collections: list[str] | None = None,
    ) -> None:
        jobs: list[dict[str, object]] = [
            {
                "id": f"job-{index}",
                "original_name": f"audio-{index}.m4a",
                "filename": f"job-{index}-audio.m4a",
                "created_at": stamp,
                "model": "large-v3",
                "diarize": True,
            }
            for index, stamp in enumerate(created_at)
        ]
        for job, status in zip(jobs, statuses or []):
            job["status"] = status
        for job, collection in zip(jobs, collections or []):
            job["collection"] = collection
        (root / "jobs.json").write_text(json.dumps(jobs))

    return write
