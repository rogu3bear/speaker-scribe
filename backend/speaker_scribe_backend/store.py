from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Callable

from pydantic import TypeAdapter

from .models import Job

JobMutator = Callable[[Job], Job]

INTERRUPTED_ERROR = "Job was interrupted by a server restart."


class JobStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.upload_dir = root / "uploads"
        self.jobs_path = root / "jobs.json"
        self._lock = threading.Lock()
        self.root.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def list_jobs(self) -> list[Job]:
        with self._lock:
            jobs = self._read_jobs()
        return sorted(jobs, key=lambda job: job.created_at, reverse=True)

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return next((job for job in self._read_jobs() if job.id == job_id), None)

    def save(self, job: Job) -> Job:
        with self._lock:
            jobs = [item for item in self._read_jobs() if item.id != job.id]
            jobs.append(job)
            self._write_jobs(jobs)
        return job

    def mutate(self, job_id: str, mutator: JobMutator) -> Job | None:
        with self._lock:
            jobs = self._read_jobs()
            for index, job in enumerate(jobs):
                if job.id == job_id:
                    updated = mutator(job)
                    jobs[index] = updated
                    self._write_jobs(jobs)
                    return updated
        return None

    def fail_interrupted_jobs(self) -> list[str]:
        """Mark jobs left mid-flight by a previous process as failed.

        A job's progress lives only in its worker thread, so a restart orphans
        anything still queued or running. Without this sweep those jobs stay
        `running` forever and the UI polls them indefinitely.
        """
        with self._lock:
            jobs = self._read_jobs()
            interrupted: list[str] = []
            for index, job in enumerate(jobs):
                if job.status not in ("queued", "running"):
                    continue
                jobs[index] = job.model_copy(
                    update={
                        "status": "failed",
                        "progress": 1,
                        "stage": "Transcript failed",
                        "error": INTERRUPTED_ERROR,
                    }
                )
                interrupted.append(job.id)
            if interrupted:
                self._write_jobs(jobs)
        return interrupted

    def _read_jobs(self) -> list[Job]:
        if not self.jobs_path.exists():
            return []
        raw = json.loads(self.jobs_path.read_text())
        return TypeAdapter(list[Job]).validate_python(raw)

    def _write_jobs(self, jobs: list[Job]) -> None:
        self.jobs_path.write_text(
            json.dumps([job.model_dump(mode="json") for job in jobs], indent=2) + "\n"
        )
