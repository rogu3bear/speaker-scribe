"""Local-only regression guard for the diarization stack.

The diarizer rests on constants chosen by reasoning rather than measurement
(`WINDOW_SECONDS`, `HOP_SECONDS`, `SINGLE_SPEAKER_SILHOUETTE`,
`MIN_SPEAKER_DISTANCE`, `MERGE_GAP_SECONDS`). This test freezes the turns the
diarizer produces for one real recording so a change to any of them becomes
visible and quantified instead of invisible.

It snapshots `LocalDiarizer.diarize` rather than a transcript: that isolates
VAD, embeddings, clustering and merging — where those constants live — avoids
Whisper's decoding nondeterminism, and skips the slow transcription step.

Speaker Scribe is a public repository, so nothing here is committed. Both the
audio and the expectations live under the gitignored `data/` tree.

Set up once:

    cp <your recording> data/fixtures/golden-audio.m4a
    SPEAKER_SCRIBE_WRITE_GOLDEN=1 uv run --extra ml --extra test \\
        pytest backend/tests/test_diarize_golden.py

Then it guards every later run. Regenerate deliberately with the same command
after an intended change.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from speaker_scribe_backend import diarize
from speaker_scribe_backend.diarize import LocalDiarizer
from speaker_scribe_backend.diarize import SpeakerTurn
from speaker_scribe_backend.models import TranscribeOptions

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "data" / "fixtures"
GOLDEN_PATH = FIXTURE_DIR / "diarization-golden.json"

SAMPLE_STEP_SECONDS = 1.0
SPEAKER_SECONDS_TOLERANCE = 0.02

# The pipeline is deterministic — repeated runs agree exactly — so this only has
# to leave room for dependency drift, not for run-to-run noise. At 0.98 it was
# inert: a 17% change to WINDOW_SECONDS still scored 0.9839 and passed.
MIN_TIMELINE_AGREEMENT = 0.99

# Recorded alongside the golden so a drop in agreement can be explained by
# looking at what actually moved.
TRACKED_CONSTANTS = [
    "WINDOW_SECONDS",
    "HOP_SECONDS",
    "MIN_WINDOW_SECONDS",
    "MERGE_GAP_SECONDS",
    "SINGLE_SPEAKER_SILHOUETTE",
    "MIN_SPEAKER_DISTANCE",
    "DEFAULT_MAX_SPEAKERS",
    "EMBEDDING_MODEL",
]


def golden_audio() -> Path | None:
    override = os.getenv("SPEAKER_SCRIBE_GOLDEN_AUDIO")
    if override:
        path = Path(override)
        return path if path.exists() else None
    return next(iter(sorted(FIXTURE_DIR.glob("golden-audio.*"))), None)


def current_constants() -> dict[str, object]:
    return {name: getattr(diarize, name) for name in TRACKED_CONSTANTS}


def speaker_seconds(turns: list[SpeakerTurn]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for turn in turns:
        totals[turn.speaker] = totals.get(turn.speaker, 0.0) + max(0.0, turn.end - turn.start)
    return {speaker: round(seconds, 2) for speaker, seconds in sorted(totals.items())}


def timeline(turns: list[SpeakerTurn], end: float) -> list[str | None]:
    """Who is speaking at each sample point, or None inside a silence."""
    marks: list[str | None] = []
    position = 0.0
    while position < end:
        marks.append(
            next(
                (turn.speaker for turn in turns if turn.start <= position < turn.end),
                None,
            )
        )
        position += SAMPLE_STEP_SECONDS
    return marks


def agreement(left: list[str | None], right: list[str | None]) -> float:
    """Fraction of sample points where two timelines name the same speaker."""
    if not left and not right:
        return 1.0
    width = max(len(left), len(right))
    padded_left = left + [None] * (width - len(left))
    padded_right = right + [None] * (width - len(right))
    matches = sum(1 for a, b in zip(padded_left, padded_right) if a == b)
    return matches / width


def to_turns(raw: list[list]) -> list[SpeakerTurn]:
    return [SpeakerTurn(start=item[0], end=item[1], speaker=item[2]) for item in raw]


def test_diarization_matches_the_recorded_baseline() -> None:
    pytest.importorskip("sklearn")
    pytest.importorskip("speechbrain")
    pytest.importorskip("silero_vad")

    audio = golden_audio()
    if audio is None:
        pytest.skip(
            "no golden audio; copy a recording to data/fixtures/golden-audio.* "
            "or set SPEAKER_SCRIBE_GOLDEN_AUDIO"
        )

    writing = os.getenv("SPEAKER_SCRIBE_WRITE_GOLDEN") == "1"
    if not writing and not GOLDEN_PATH.exists():
        pytest.skip(f"no baseline at {GOLDEN_PATH}; regenerate with SPEAKER_SCRIBE_WRITE_GOLDEN=1")

    turns = LocalDiarizer().diarize(
        audio,
        TranscribeOptions(model="large-v3", diarize=True),
        lambda value, stage: None,
    )
    assert turns, "diarization produced no speaker turns"

    if writing:
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        GOLDEN_PATH.write_text(
            json.dumps(
                {
                    "audio": audio.name,
                    "constants": current_constants(),
                    "speaker_seconds": speaker_seconds(turns),
                    "turns": [[turn.start, turn.end, turn.speaker] for turn in turns],
                },
                indent=2,
            )
            + "\n"
        )
        pytest.skip(f"wrote baseline to {GOLDEN_PATH}")

    golden = json.loads(GOLDEN_PATH.read_text())
    expected = to_turns(golden["turns"])

    changed = {
        name: (was, now)
        for name, now in current_constants().items()
        if (was := golden.get("constants", {}).get(name)) != now
    }

    # Assert the configuration directly. Comparing output alone cannot cover the
    # constants reliably: a clean two-speaker recording sits nowhere near
    # MIN_SPEAKER_DISTANCE or SINGLE_SPEAKER_SILHOUETTE, so loosening either
    # changes nothing observable. This makes every tracked constant guarded.
    assert not changed, (
        f"tracked diarization constants changed: {changed}. The baseline no longer "
        "describes this configuration. Regenerate it with "
        "SPEAKER_SCRIBE_WRITE_GOLDEN=1 if the change is intended."
    )

    expected_seconds = golden["speaker_seconds"]
    actual_seconds = speaker_seconds(turns)

    assert set(actual_seconds) == set(expected_seconds), (
        f"speaker count changed: {sorted(expected_seconds)} -> {sorted(actual_seconds)}; "
        f"constants changed: {changed or 'none'}"
    )

    for speaker, expected_total in expected_seconds.items():
        assert actual_seconds[speaker] == pytest.approx(
            expected_total, rel=SPEAKER_SECONDS_TOLERANCE
        ), f"{speaker} talk time moved; constants changed: {changed or 'none'}"

    end = max(turn.end for turn in expected + turns)
    score = agreement(timeline(expected, end), timeline(turns, end))
    assert score >= MIN_TIMELINE_AGREEMENT, (
        f"timeline agreement {score:.1%} is below {MIN_TIMELINE_AGREEMENT:.0%}; "
        f"constants changed: {changed or 'none'}. Regenerate with "
        f"SPEAKER_SCRIBE_WRITE_GOLDEN=1 if this change is intended."
    )
