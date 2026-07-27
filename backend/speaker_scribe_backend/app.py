from __future__ import annotations

import os
import re
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi import File
from fastapi import Form
from fastapi import HTTPException
from fastapi import UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import Response

from .exporters import export_json
from .exporters import export_srt
from .exporters import export_txt
from .models import FileJobRequest
from .models import HealthResponse
from .models import Job
from .models import JobCollection
from .models import SpeakerRenameRequest
from .models import TranscribeOptions
from .pipeline import create_transcriber
from .pipeline import ml_ready
from .store import JobStore
from .transcript import with_clean_text


@dataclass(frozen=True)
class AppSettings:
    data_root: Path
    max_upload_mb: int

    @classmethod
    def from_env(cls) -> "AppSettings":
        return cls(
            data_root=Path(os.getenv("SPEAKER_SCRIBE_DATA", "data")).resolve(),
            max_upload_mb=int(os.getenv("SPEAKER_SCRIBE_MAX_UPLOAD_MB", "500")),
        )


@asynccontextmanager
async def lifespan(api: FastAPI) -> AsyncIterator[None]:
    # Worker threads do not survive a restart, so anything still in flight is dead.
    # This runs on server startup rather than at import, so that merely importing
    # this module — as any pytest run from the repository root does — cannot
    # rewrite a store that another process is actively working on.
    api.state.store.fail_interrupted_jobs()
    yield


app = FastAPI(title="Speaker Scribe API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5178", "http://localhost:5178"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.settings = AppSettings.from_env()
app.state.store = JobStore(app.state.settings.data_root)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    ready, detail = ml_ready()
    return HealthResponse(
        ok=True,
        engine=os.getenv("SPEAKER_SCRIBE_ENGINE", "mlx"),
        ml_ready=ready,
        detail=detail,
    )


@app.get("/api/jobs", response_model=list[Job])
def list_jobs(collection: JobCollection | None = None) -> list[Job]:
    jobs = get_store().list_jobs()
    if collection is not None:
        jobs = [job for job in jobs if job.collection == collection]
    return [_with_audio_url(job) for job in jobs]


@app.get("/api/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    job = get_store().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _with_audio_url(job)


@app.post("/api/jobs", response_model=Job)
def create_job(
    file: UploadFile = File(...),
    model: str = Form("large-v3"),
    diarize: bool = Form(True),
    min_speakers: int | None = Form(None),
    max_speakers: int | None = Form(None),
    language: str | None = Form(None),
) -> Job:
    store = get_store()
    original_name = Path(file.filename or "audio").name
    safe_name = _safe_filename(original_name)
    job_id = uuid4().hex
    stored_name = f"{job_id}-{safe_name}"
    upload_path = store.upload_dir / stored_name

    options = TranscribeOptions(
        model=model,
        diarize=diarize,
        min_speakers=min_speakers,
        max_speakers=max_speakers,
        language=language or None,
    )
    if (
        options.min_speakers is not None
        and options.max_speakers is not None
        and options.min_speakers > options.max_speakers
    ):
        raise HTTPException(status_code=422, detail="min_speakers cannot exceed max_speakers")

    _save_upload(file, upload_path, get_settings().max_upload_mb)

    job = Job(
        id=job_id,
        original_name=original_name,
        filename=stored_name,
        created_at=datetime.now(UTC),
        model=options.model,
        diarize=options.diarize,
        language=options.language,
    )
    store.save(job)

    thread = threading.Thread(target=_run_job, args=(store, job_id, upload_path, options), daemon=True)
    thread.start()
    return _with_audio_url(job)


@app.patch("/api/jobs/{job_id}/speakers", response_model=Job)
def update_speakers(job_id: str, request: SpeakerRenameRequest) -> Job:
    def mutate(job: Job) -> Job:
        next_speakers = []
        for speaker in job.speakers:
            if speaker.id in request.speakers:
                next_speakers.append(speaker.model_copy(update={"name": request.speakers[speaker.id]}))
            else:
                next_speakers.append(speaker)
        return job.model_copy(update={"speakers": next_speakers})

    updated = get_store().mutate(job_id, mutate)
    if updated is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _with_audio_url(updated)


@app.patch("/api/jobs/{job_id}/collection", response_model=Job)
def file_job(job_id: str, request: FileJobRequest) -> Job:
    """Move a job between the inbox, saved conversations, and the archive."""

    def mutate(job: Job) -> Job:
        update: dict[str, object] = {"collection": request.collection}
        if request.title is not None:
            update["title"] = request.title.strip() or None
        return job.model_copy(update=update)

    updated = get_store().mutate(job_id, mutate)
    if updated is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _with_audio_url(updated)


@app.get("/api/jobs/{job_id}/audio")
def get_audio(job_id: str) -> FileResponse:
    store = get_store()
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    path = store.upload_dir / job.filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(path, filename=job.original_name)


@app.get("/api/jobs/{job_id}/export")
def export_job(job_id: str, format: str = "txt") -> Response:
    job = get_store().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    normalized = format.lower()
    if normalized == "txt":
        return Response(export_txt(job), media_type="text/plain")
    if normalized == "srt":
        return Response(export_srt(job), media_type="application/x-subrip")
    if normalized == "json":
        return Response(export_json(job), media_type="application/json")
    raise HTTPException(status_code=422, detail="format must be txt, srt, or json")


def _run_job(
    store: JobStore,
    job_id: str,
    upload_path: Path,
    options: TranscribeOptions,
) -> None:
    def update(progress: float, stage: str) -> None:
        store.mutate(
            job_id,
            lambda job: job.model_copy(
                update={
                    "status": "running",
                    "progress": max(0.0, min(0.99, progress)),
                    "stage": stage,
                }
            ),
        )

    try:
        update(0.03, "Starting transcript job")
        result = create_transcriber().transcribe(upload_path, options, update)
        store.mutate(
            job_id,
            lambda job: job.model_copy(
                update={
                    "status": "completed",
                    "progress": 1,
                    "stage": "Transcript complete",
                    "error": None,
                    "language": result.language or job.language,
                    "duration": result.duration,
                    "speakers": result.speakers,
                    "segments": result.segments,
                }
            ),
        )
    except Exception as exc:  # noqa: BLE001 - surfaced as job state for the UI.
        store.mutate(
            job_id,
            lambda job: job.model_copy(
                update={
                    "status": "failed",
                    "progress": 1,
                    "stage": "Transcript failed",
                    "error": str(exc),
                }
            ),
        )


def _with_audio_url(job: Job) -> Job:
    """Shape a stored job for the API: derived fields are added here, not persisted."""
    return job.model_copy(
        update={
            "audio_url": f"/api/jobs/{job.id}/audio",
            "segments": with_clean_text(job.segments),
        }
    )


def _safe_filename(filename: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip("-._")
    return stem or "audio"


def _save_upload(file: UploadFile, destination: Path, max_upload_mb: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    limit = max_upload_mb * 1024 * 1024
    with destination.open("wb") as output:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                output.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"Upload exceeds {max_upload_mb} MB")
            output.write(chunk)
    file.file.close()
    if destination.stat().st_size == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Audio file is empty")


def get_settings() -> AppSettings:
    return app.state.settings


def get_store() -> JobStore:
    return app.state.store
