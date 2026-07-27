import json
from pathlib import Path

from speaker_scribe_backend.store import JobStore


def write_jobs(root: Path, created_at: list[str]) -> None:
    jobs = [
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
    (root / "jobs.json").write_text(json.dumps(jobs))


def test_list_jobs_sorts_store_with_mixed_timezone_awareness(tmp_path: Path) -> None:
    """Rows written before the switch to datetime.now(UTC) are naive.

    Sorting a store holding both naive and aware timestamps used to raise
    TypeError, which surfaced as a 500 on GET /api/jobs.
    """
    store = JobStore(tmp_path)
    write_jobs(
        tmp_path,
        [
            "2026-06-23T02:35:23.502870",  # naive, legacy row
            "2026-07-27T18:42:13.126781Z",  # aware, current row
        ],
    )

    jobs = store.list_jobs()

    assert [job.id for job in jobs] == ["job-1", "job-0"]
    assert all(job.created_at.tzinfo is not None for job in jobs)


def test_list_jobs_orders_newest_first(tmp_path: Path) -> None:
    store = JobStore(tmp_path)
    write_jobs(
        tmp_path,
        [
            "2026-07-01T00:00:00Z",
            "2026-07-03T00:00:00Z",
            "2026-07-02T00:00:00Z",
        ],
    )

    assert [job.id for job in store.list_jobs()] == ["job-1", "job-2", "job-0"]
