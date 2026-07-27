from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

JobStatus = Literal["queued", "running", "completed", "failed"]


class TranscribeOptions(BaseModel):
    model: str = "large-v3"
    diarize: bool = True
    min_speakers: int | None = Field(default=None, ge=1, le=12)
    max_speakers: int | None = Field(default=None, ge=1, le=12)
    language: str | None = None


class TranscriptSegment(BaseModel):
    id: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str
    speaker: str = "SPEAKER_00"


class Speaker(BaseModel):
    id: str
    name: str
    color: str
    seconds: float = Field(default=0, ge=0)


class Job(BaseModel):
    id: str
    original_name: str
    filename: str
    created_at: datetime
    status: JobStatus = "queued"
    progress: float = Field(default=0, ge=0, le=1)
    stage: str = "Queued"
    error: str | None = None
    model: str
    diarize: bool
    language: str | None = None
    duration: float | None = None
    audio_url: str | None = None
    speakers: list[Speaker] = Field(default_factory=list)
    segments: list[TranscriptSegment] = Field(default_factory=list)

    @field_validator("created_at")
    @classmethod
    def _ensure_aware(cls, value: datetime) -> datetime:
        """Treat stored naive timestamps as UTC.

        Jobs written before the switch to `datetime.now(UTC)` are naive, and
        sorting a store that holds both kinds raises TypeError. Normalizing on
        read keeps old and new rows comparable without rewriting the file.
        """
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class SpeakerRenameRequest(BaseModel):
    speakers: dict[str, str]


class HealthResponse(BaseModel):
    ok: bool
    engine: str
    ml_ready: bool
    detail: str | None = None
