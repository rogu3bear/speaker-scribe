from pathlib import Path

from fastapi.testclient import TestClient

from speaker_scribe_backend import app as app_module
from speaker_scribe_backend.app import AppSettings
from speaker_scribe_backend.store import INTERRUPTED_ERROR
from speaker_scribe_backend.store import JobStore


def test_list_jobs_sorts_store_with_mixed_timezone_awareness(tmp_path: Path, write_jobs) -> None:
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


def test_fail_interrupted_jobs_sweeps_queued_and_running(tmp_path: Path, write_jobs) -> None:
    store = JobStore(tmp_path)
    write_jobs(
        tmp_path,
        ["2026-07-01T00:00:00Z", "2026-07-02T00:00:00Z"],
        statuses=["queued", "running"],
    )

    interrupted = store.fail_interrupted_jobs()

    assert sorted(interrupted) == ["job-0", "job-1"]
    for job in store.list_jobs():
        assert job.status == "failed"
        assert job.error == INTERRUPTED_ERROR
        assert job.progress == 1
        assert job.stage == "Transcript failed"


def test_fail_interrupted_jobs_leaves_finished_jobs_alone(tmp_path: Path, write_jobs) -> None:
    store = JobStore(tmp_path)
    write_jobs(
        tmp_path,
        ["2026-07-01T00:00:00Z", "2026-07-02T00:00:00Z"],
        statuses=["completed", "failed"],
    )

    assert store.fail_interrupted_jobs() == []
    assert [job.status for job in store.list_jobs()] == ["failed", "completed"]
    assert all(job.error != INTERRUPTED_ERROR for job in store.list_jobs())


def test_fail_interrupted_jobs_does_not_write_an_untouched_store(tmp_path: Path, write_jobs) -> None:
    store = JobStore(tmp_path)
    write_jobs(tmp_path, ["2026-07-01T00:00:00Z"], statuses=["completed"])
    before = (tmp_path / "jobs.json").read_text()

    assert store.fail_interrupted_jobs() == []
    assert (tmp_path / "jobs.json").read_text() == before


def test_fail_interrupted_jobs_handles_an_empty_store(tmp_path: Path, write_jobs) -> None:
    assert JobStore(tmp_path).fail_interrupted_jobs() == []


def use_store(tmp_path: Path) -> None:
    app_module.app.state.settings = AppSettings(data_root=tmp_path, max_upload_mb=1)
    app_module.app.state.store = JobStore(tmp_path)


def test_server_startup_reports_a_job_orphaned_by_a_restart_as_failed(tmp_path: Path, write_jobs) -> None:
    """The lifespan sweep runs on server startup, so a restart heals the store."""
    write_jobs(tmp_path, ["2026-07-01T00:00:00Z"], statuses=["running"])
    use_store(tmp_path)

    # Entering the client context is what runs the lifespan handler.
    with TestClient(app_module.app) as client:
        body = client.get("/api/jobs/job-0").json()

    assert body["status"] == "failed"
    assert body["error"] == INTERRUPTED_ERROR


def test_importing_the_app_never_rewrites_a_store(tmp_path: Path, write_jobs) -> None:
    """A bare import must not touch a store another process may be working on.

    The sweep used to run at module scope, so any pytest run from the repository
    root rewrote the developer's live jobs.json — and could mark a genuinely
    running job as interrupted underneath the process still working on it.
    """
    write_jobs(tmp_path, ["2026-07-01T00:00:00Z"], statuses=["running"])
    before = (tmp_path / "jobs.json").read_text()
    use_store(tmp_path)

    TestClient(app_module.app)  # constructed, never entered: no lifespan, no sweep

    assert (tmp_path / "jobs.json").read_text() == before


def test_list_jobs_orders_newest_first(tmp_path: Path, write_jobs) -> None:
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
