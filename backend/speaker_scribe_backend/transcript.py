from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from .cleanup import clean_text
from .cleanup import is_sentence_end
from .models import Speaker
from .models import TranscriptSegment


def build_segment(
    segment_id: str, start: float, end: float, text: str, speaker: str
) -> TranscriptSegment:
    """Build a stored segment. `clean_text` is derived on read, never persisted."""
    return TranscriptSegment(
        id=segment_id,
        start=round(start, 2),
        end=round(end, 2),
        text=text,
        speaker=speaker,
    )


def with_clean_text(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    """Derive the tidied rendering of each segment.

    Cleanup is applied here rather than at transcription time so that improving a
    rule improves every transcript already on disk, including ones recorded before
    the rule existed. Storing it instead would freeze each transcript against
    whatever the rules happened to be the day it was made, and would make tuning
    them cost a full re-transcription.
    """
    derived: list[TranscriptSegment] = []
    for index, segment in enumerate(segments):
        previous = segments[index - 1] if index else None
        continues = (
            previous is not None
            and previous.speaker == segment.speaker
            and not is_sentence_end(previous.text)
        )
        derived.append(
            segment.model_copy(
                update={"clean_text": clean_text(segment.text, starts_sentence=not continues)}
            )
        )
    return derived

SPEAKER_COLORS = [
    "#0f766e",
    "#b45309",
    "#315d75",
    "#7c3aed",
    "#be123c",
    "#047857",
    "#a16207",
    "#4338ca",
]


def segment_duration(segment: TranscriptSegment) -> float:
    return max(0.0, segment.end - segment.start)


def build_speakers(segments: Iterable[TranscriptSegment]) -> list[Speaker]:
    totals: dict[str, float] = defaultdict(float)
    for segment in segments:
        totals[segment.speaker] += segment_duration(segment)

    speakers: list[Speaker] = []
    for index, speaker_id in enumerate(sorted(totals)):
        speakers.append(
            Speaker(
                id=speaker_id,
                name=speaker_id.replace("_", " ").title(),
                color=SPEAKER_COLORS[index % len(SPEAKER_COLORS)],
                seconds=round(totals[speaker_id], 2),
            )
        )
    return speakers


def normalize_transcription_result(result: dict[str, Any]) -> tuple[list[TranscriptSegment], float | None]:
    raw_segments = result.get("segments") or []
    normalized: list[TranscriptSegment] = []

    for segment_index, segment in enumerate(raw_segments):
        words = [word for word in segment.get("words", []) if word.get("word")]
        if words:
            normalized.extend(_segments_from_words(segment_index, words))
            continue

        start = float(segment.get("start") or 0)
        end = float(segment.get("end") or start)
        text = str(segment.get("text") or "").strip()
        speaker = str(segment.get("speaker") or "SPEAKER_00")
        if text:
            normalized.append(
                build_segment(f"seg-{segment_index + 1}", start, end, text, speaker)
            )

    duration = None
    if normalized:
        duration = max(segment.end for segment in normalized)
    return normalized, duration


def _segments_from_words(segment_index: int, words: list[dict[str, Any]]) -> list[TranscriptSegment]:
    grouped: list[TranscriptSegment] = []
    current_speaker: str | None = None
    current_words: list[str] = []
    current_start = 0.0
    current_end = 0.0
    group_index = 0

    def flush() -> None:
        nonlocal group_index
        if not current_words or current_speaker is None:
            return
        group_index += 1
        grouped.append(
            build_segment(
                f"seg-{segment_index + 1}-{group_index}",
                current_start,
                current_end,
                _join_words(current_words),
                current_speaker,
            )
        )

    for word in words:
        speaker = str(word.get("speaker") or "SPEAKER_00")
        start = float(word.get("start") or current_end or 0)
        end = float(word.get("end") or start)
        text = str(word.get("word") or "").strip()
        if not text:
            continue

        if current_speaker is None:
            current_speaker = speaker
            current_start = start
        elif speaker != current_speaker:
            flush()
            current_words = []
            current_speaker = speaker
            current_start = start

        current_words.append(text)
        current_end = end

    flush()
    return grouped


def _join_words(words: list[str]) -> str:
    text = " ".join(words)
    for punctuation in [".", ",", "?", "!", ":", ";"]:
        text = text.replace(f" {punctuation}", punctuation)
    text = text.replace(" n't", "n't").replace(" '", "'")
    return text.strip()
