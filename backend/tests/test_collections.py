from pathlib import Path

from fastapi.testclient import TestClient

from speaker_scribe_backend import app as app_module
from speaker_scribe_backend.app import AppSettings
from speaker_scribe_backend.models import Job
from speaker_scribe_backend.store import JobStore


def client_over(tmp_path: Path) -> TestClient:
    app_module.app.state.settings = AppSettings(data_root=tmp_path, max_upload_mb=1)
    app_module.app.state.store = JobStore(tmp_path)
    return TestClient(app_module.app)


def test_a_new_job_starts_in_the_inbox(tmp_path: Path, write_jobs) -> None:
    client = client_over(tmp_path)
    write_jobs(tmp_path, ["2026-07-01T00:00:00Z"])

    assert client.get("/api/jobs/job-0").json()["collection"] == "inbox"


def test_saving_a_job_files_it_as_a_conversation(tmp_path: Path, write_jobs) -> None:
    client = client_over(tmp_path)
    write_jobs(tmp_path, ["2026-07-01T00:00:00Z"])

    body = client.patch(
        "/api/jobs/job-0/collection",
        json={"collection": "saved", "title": "Donella interview"},
    ).json()

    assert body["collection"] == "saved"
    assert body["title"] == "Donella interview"


def test_archiving_a_job_moves_it_out_of_the_inbox(tmp_path: Path, write_jobs) -> None:
    client = client_over(tmp_path)
    write_jobs(tmp_path, ["2026-07-01T00:00:00Z", "2026-07-02T00:00:00Z"])

    client.patch("/api/jobs/job-0/collection", json={"collection": "archived"})

    inbox = client.get("/api/jobs", params={"collection": "inbox"}).json()
    archived = client.get("/api/jobs", params={"collection": "archived"}).json()

    assert [job["id"] for job in inbox] == ["job-1"]
    assert [job["id"] for job in archived] == ["job-0"]


def test_listing_without_a_filter_returns_every_collection(tmp_path: Path, write_jobs) -> None:
    client = client_over(tmp_path)
    write_jobs(tmp_path, ["2026-07-01T00:00:00Z", "2026-07-02T00:00:00Z"])
    client.patch("/api/jobs/job-0/collection", json={"collection": "archived"})

    assert len(client.get("/api/jobs").json()) == 2


def test_filing_is_reversible(tmp_path: Path, write_jobs) -> None:
    """Archiving hides a job; it must never be a one-way door."""
    client = client_over(tmp_path)
    write_jobs(tmp_path, ["2026-07-01T00:00:00Z"])

    client.patch("/api/jobs/job-0/collection", json={"collection": "archived"})
    body = client.patch("/api/jobs/job-0/collection", json={"collection": "inbox"}).json()

    assert body["collection"] == "inbox"


def test_filing_preserves_the_transcript(tmp_path: Path, write_jobs) -> None:
    """Moving between collections must not touch the transcript itself."""
    store = JobStore(tmp_path)
    client = client_over(tmp_path)
    store.save(
        Job(
            id="job-x",
            original_name="talk.m4a",
            filename="job-x-talk.m4a",
            created_at="2026-07-01T00:00:00Z",
            model="large-v3",
            diarize=True,
            status="completed",
            segments=[{"id": "s1", "start": 0, "end": 2, "text": "um hello there"}],
        )
    )

    body = client.patch("/api/jobs/job-x/collection", json={"collection": "saved"}).json()

    assert body["segments"][0]["text"] == "um hello there"
    assert body["segments"][0]["clean_text"] == "Hello there"


def test_retitling_without_moving_keeps_the_collection(tmp_path: Path, write_jobs) -> None:
    client = client_over(tmp_path)
    write_jobs(tmp_path, ["2026-07-01T00:00:00Z"])
    client.patch("/api/jobs/job-0/collection", json={"collection": "saved", "title": "First"})

    body = client.patch(
        "/api/jobs/job-0/collection", json={"collection": "saved", "title": "Second"}
    ).json()

    assert body["collection"] == "saved"
    assert body["title"] == "Second"


def test_a_blank_title_clears_back_to_the_file_name(tmp_path: Path, write_jobs) -> None:
    client = client_over(tmp_path)
    write_jobs(tmp_path, ["2026-07-01T00:00:00Z"])
    client.patch("/api/jobs/job-0/collection", json={"collection": "saved", "title": "Named"})

    body = client.patch(
        "/api/jobs/job-0/collection", json={"collection": "saved", "title": "   "}
    ).json()

    assert body["title"] is None


def test_filing_an_unknown_job_is_a_404(tmp_path: Path, write_jobs) -> None:
    client = client_over(tmp_path)

    assert client.patch("/api/jobs/nope/collection", json={"collection": "saved"}).status_code == 404


def test_an_unknown_collection_is_rejected(tmp_path: Path, write_jobs) -> None:
    client = client_over(tmp_path)
    write_jobs(tmp_path, ["2026-07-01T00:00:00Z"])

    response = client.patch("/api/jobs/job-0/collection", json={"collection": "trash"})

    assert response.status_code == 422
