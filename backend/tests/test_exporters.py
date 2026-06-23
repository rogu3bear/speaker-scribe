from datetime import datetime

from speaker_scribe_backend.exporters import export_srt
from speaker_scribe_backend.exporters import export_txt
from speaker_scribe_backend.exporters import format_srt_time
from speaker_scribe_backend.models import Job
from speaker_scribe_backend.models import Speaker
from speaker_scribe_backend.models import TranscriptSegment


def make_job() -> Job:
    return Job(
        id="job-1",
        original_name="meeting.wav",
        filename="meeting.wav",
        created_at=datetime(2026, 6, 23),
        model="large-v3",
        diarize=True,
        speakers=[Speaker(id="SPEAKER_00", name="Ari", color="#0f766e", seconds=2)],
        segments=[
            TranscriptSegment(
                id="seg-1",
                start=1.25,
                end=3.5,
                speaker="SPEAKER_00",
                text="Opening line.",
            )
        ],
    )


def test_format_srt_time() -> None:
    assert format_srt_time(3661.234) == "01:01:01,234"


def test_exports_use_renamed_speaker() -> None:
    job = make_job()

    assert "Ari: Opening line." in export_txt(job)
    assert "Ari: Opening line." in export_srt(job)
