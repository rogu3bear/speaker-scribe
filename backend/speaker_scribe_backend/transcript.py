from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from .models import Speaker
from .models import TranscriptSegment

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


def normalize_whispermlx_result(result: dict[str, Any]) -> tuple[list[TranscriptSegment], float | None]:
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
                TranscriptSegment(
                    id=f"seg-{segment_index + 1}",
                    start=round(start, 2),
                    end=round(end, 2),
                    text=text,
                    speaker=speaker,
                )
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
            TranscriptSegment(
                id=f"seg-{segment_index + 1}-{group_index}",
                start=round(current_start, 2),
                end=round(current_end, 2),
                text=_join_words(current_words),
                speaker=current_speaker,
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
