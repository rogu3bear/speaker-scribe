#!/usr/bin/env python
"""Build a throwaway job store containing one invented conversation.

Used to record the README demo. Everything here is fiction: the speakers, the
words, and the file name. Nothing from a real recording is involved, and the
store is written somewhere separate so a real one is never touched.

    uv run --extra ml python scripts/make-demo-store.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import UTC
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from speaker_scribe_backend.models import Job  # noqa: E402
from speaker_scribe_backend.store import JobStore  # noqa: E402
from speaker_scribe_backend.transcript import build_segment  # noqa: E402
from speaker_scribe_backend.transcript import build_speakers  # noqa: E402

STORE = Path(__file__).resolve().parents[1] / "data" / "demo-store"

# An invented design review. Written verbatim, fillers and all, so the tidy
# toggle has something real to do.
SCRIPT: list[tuple[str, str]] = [
    ("SPEAKER_00", "Okay so, um, thanks for making the time."),
    ("SPEAKER_00", "I wanted to walk through the onboarding flow before we commit to it."),
    ("SPEAKER_01", "Yeah, of course."),
    ("SPEAKER_01", "I mean, I've been staring at it all week, so, uh, fair warning."),
    ("SPEAKER_00", "That's exactly why I want fresh eyes on it."),
    ("SPEAKER_00", "So the the first screen asks for an email before it shows anything."),
    ("SPEAKER_01", "Right, and that's the part I keep going back and forth on."),
    ("SPEAKER_01", "You know, we lose about forty percent of people right there."),
    ("SPEAKER_02", "Sorry, is that forty percent of signups or forty percent of visits?"),
    ("SPEAKER_01", "Visits. Signups are, um, a much smaller number obviously."),
    ("SPEAKER_02", "Okay, that changes how I'd read it."),
    ("SPEAKER_00", "Can we show the workspace first and ask for the email at save time?"),
    ("SPEAKER_01", "We can, it's, uh, maybe two days of work."),
    ("SPEAKER_01", "The wh- what worries me is the empty state looks broken without data."),
    ("SPEAKER_00", "Then we seed it with a sample project."),
    ("SPEAKER_00", "People understand a demo. They don't understand a blank page."),
    ("SPEAKER_02", "I like that. It also gives us something to point at in the docs."),
    ("SPEAKER_01", "Alright. Let me sketch it and we'll look again on Thursday."),
]

# A second, older conversation, so the Inbox and Conversations tabs are both
# populated rather than one of them reading "No jobs yet".
STANDUP: list[tuple[str, str]] = [
    ("SPEAKER_00", "Quick one today. Where are we on the import job?"),
    ("SPEAKER_01", "It's, um, running green since Tuesday. No retries."),
    ("SPEAKER_00", "Good. Anything blocking?"),
    ("SPEAKER_01", "Only the staging credentials, which I'll chase this morning."),
]

WORDS_PER_SECOND = 2.6


NAMES = {"SPEAKER_00": "Dana", "SPEAKER_01": "Priya", "SPEAKER_02": "Marcus"}


def transcribe(script: list[tuple[str, str]]):
    segments = []
    clock = 1.4
    for index, (speaker, text) in enumerate(script, start=1):
        length = max(1.6, len(text.split()) / WORDS_PER_SECOND)
        segments.append(build_segment(f"seg-{index}", clock, clock + length, text, speaker))
        clock += length + 0.45

    speakers = [
        speaker.model_copy(update={"name": NAMES.get(speaker.id, speaker.name)})
        for speaker in build_speakers(segments)
    ]
    return segments, speakers, round(clock, 2)


def main() -> None:
    STORE.mkdir(parents=True, exist_ok=True)
    store = JobStore(STORE)

    segments, speakers, clock = transcribe(SCRIPT)
    standup_segments, standup_speakers, standup_clock = transcribe(STANDUP)

    store.save(
        Job(
            id="demo0000000000000000000000000002",
            original_name="monday-standup.m4a",
            filename="monday-standup.m4a",
            created_at=datetime(2026, 3, 2, 9, 31, tzinfo=UTC),
            status="completed",
            collection="inbox",
            progress=1,
            stage="Transcript complete",
            model="large-v3-turbo",
            diarize=True,
            language="en",
            duration=standup_clock,
            speakers=standup_speakers,
            segments=standup_segments,
        )
    )

    # Silence of the right length, so the player shows a real duration instead of
    # 0:00. There is no recording to use here and inventing speech would be worse.
    audio = STORE / "uploads" / "design-review.m4a"
    audio.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("ffmpeg"):
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
             "-i", "anullsrc=r=16000:cl=mono", "-t", f"{clock:.2f}", str(audio)],
            check=True,
        )

    store.save(
        Job(
            id="demo0000000000000000000000000001",
            original_name="design-review.m4a",
            filename="design-review.m4a",
            created_at=datetime(2026, 3, 4, 15, 9, tzinfo=UTC),
            status="completed",
            collection="saved",
            title="Onboarding design review",
            progress=1,
            stage="Transcript complete",
            model="large-v3-turbo",
            diarize=True,
            language="en",
            duration=clock,
            speakers=speakers,
            segments=segments,
        )
    )
    print(
        f"wrote {STORE / 'jobs.json'} — 2 invented conversations, "
        f"{len(segments) + len(standup_segments)} segments"
    )


if __name__ == "__main__":
    main()
