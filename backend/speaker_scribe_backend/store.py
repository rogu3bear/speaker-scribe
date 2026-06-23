from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Callable

from pydantic import TypeAdapter

from .models import Job

JobMutator = Callable[[Job], Job]


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

    def _read_jobs(self) -> list[Job]:
        if not self.jobs_path.exists():
            return []
        raw = json.loads(self.jobs_path.read_text())
        return TypeAdapter(list[Job]).validate_python(raw)

    def _write_jobs(self, jobs: list[Job]) -> None:
        self.jobs_path.write_text(
            json.dumps([job.model_dump(mode="json") for job in jobs], indent=2) + "\n"
        )
