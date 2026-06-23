from __future__ import annotations

import json

from .models import Job
from .models import Speaker
from .models import TranscriptSegment


def speaker_name(speakers: list[Speaker], speaker_id: str) -> str:
    return next((speaker.name for speaker in speakers if speaker.id == speaker_id), speaker_id)


def export_txt(job: Job) -> str:
    lines = [f"# {job.original_name}", ""]
    for segment in job.segments:
        lines.append(
            f"[{format_plain_time(segment.start)} - {format_plain_time(segment.end)}] "
            f"{speaker_name(job.speakers, segment.speaker)}: {segment.text}"
        )
    return "\n".join(lines).strip() + "\n"


def export_srt(job: Job) -> str:
    chunks: list[str] = []
    for index, segment in enumerate(job.segments, start=1):
        name = speaker_name(job.speakers, segment.speaker)
        chunks.append(
            "\n".join(
                [
                    str(index),
                    f"{format_srt_time(segment.start)} --> {format_srt_time(segment.end)}",
                    f"{name}: {segment.text}",
                ]
            )
        )
    return "\n\n".join(chunks).strip() + "\n"


def export_json(job: Job) -> str:
    return json.dumps(job.model_dump(mode="json"), indent=2) + "\n"


def format_plain_time(seconds: float) -> str:
    total = max(0, int(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_srt_time(seconds: float) -> str:
    bounded = max(0.0, seconds)
    whole = int(bounded)
    millis = int(round((bounded - whole) * 1000))
    if millis == 1000:
        whole += 1
        millis = 0
    hours = whole // 3600
    minutes = (whole % 3600) // 60
    secs = whole % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
