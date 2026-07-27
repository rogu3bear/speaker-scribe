"""Fully local speaker diarization.

Silero VAD finds speech regions, SpeechBrain ECAPA turns fixed windows of those
regions into speaker embeddings, and agglomerative clustering groups the windows
into speakers. Every model here is downloaded once from a public source and runs
on-machine; nothing requires an account, a token, or a network call at inference
time.

The pure geometry helpers (`speech_windows`, `merge_turns`, `assign_speakers`)
carry no ML imports so they stay testable without the `ml` extra installed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import Any

from .models import TranscribeOptions

SAMPLE_RATE = 16_000

# Embedding windows. 1.5s is long enough for a stable ECAPA vector and short
# enough to catch a speaker change mid-sentence; the half-window hop keeps
# boundaries from landing between windows.
WINDOW_SECONDS = 1.5
HOP_SECONDS = 0.75
MIN_WINDOW_SECONDS = 0.6

# Turns from the same speaker separated by less than this are one turn.
MERGE_GAP_SECONDS = 0.4

# A turn shorter than this, with the same other speaker on both sides, is
# treated as a diarization slip rather than a real interjection. Chosen from
# measured output: on a 43-minute panel the misattributed fragments ran 0.3s to
# 1.4s, while the shortest genuine turn was around 20s. The cost is that a real
# one-word backchannel is credited to whoever holds the floor, which reads
# better than inventing a speaker for it.
SLIVER_SECONDS = 2.0

# A speaker credited with less than this in total, and a negligible share of the
# conversation, is a leftover of clustering rather than a participant.
#
# This only became safe once slivers were absorbed. Applied first it would have
# deleted a real person: on the reference panel one "speaker" was a mixture of
# three misattributed fragments and one genuine 20-second question, and a mass
# floor cannot tell those apart. After the sliver pass the same recording splits
# 1493s / 497s / 485s / 18s / 0.4s, where the smallest real voice outweighs the
# phantom 45 to 1. Both conditions must hold, so a brief but real contributor to
# a short recording keeps their share.
MIN_SPEAKER_SECONDS = 5.0
MIN_SPEAKER_SHARE = 0.01

DEFAULT_MAX_SPEAKERS = 8

# Below this silhouette score the embedding cloud has no real cluster structure,
# so a single-speaker recording is reported as one speaker instead of being
# split into invented ones. Only consulted when the caller gave no minimum.
SINGLE_SPEAKER_SILHOUETTE = 0.12

# Silhouette is scale-free: a tight, featureless cloud still splits "cleanly",
# just into meaningless halves. This absolute floor asks whether the split is
# far enough apart in ECAPA cosine space to be two different people at all.
MIN_SPEAKER_DISTANCE = 0.25

EMBEDDING_MODEL = "speechbrain/spkrec-ecapa-voxceleb"

# ECAPA runs one window at a time: measured at ~14 ms/window on CPU, and padding
# windows into batches was three times slower. Progress is reported every so many
# windows, spanning this range of the job's progress bar.
#
# Diarization owns the tail of the bar, picking up where transcription stops at
# pipeline.TRANSCRIBE_PROGRESS_END_WITH_DIARIZATION. These stay in step with it.
EMBEDDING_PROGRESS_EVERY = 64
DECODE_PROGRESS = 0.80
VAD_PROGRESS = 0.82
EMBEDDING_PROGRESS_START = 0.84
EMBEDDING_PROGRESS_END = 0.94
CLUSTERING_PROGRESS = 0.95


@dataclass(frozen=True)
class SpeakerTurn:
    start: float
    end: float
    speaker: str


def speaker_label(index: int) -> str:
    return f"SPEAKER_{index:02d}"


def model_cache_dir() -> Path:
    root = os.getenv("SPEAKER_SCRIBE_MODEL_CACHE")
    if root:
        return Path(root).expanduser()
    return Path.home() / ".cache" / "speaker-scribe"


def load_audio_16k(audio_path: Path) -> Any:
    """Decode any ffmpeg-readable file to mono float32 PCM at 16 kHz."""
    import numpy as np

    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg was not found on PATH. Install it with `brew install ffmpeg` "
            "before running real transcription."
        )

    command = [
        "ffmpeg",
        "-nostdin",
        "-threads",
        "0",
        "-i",
        str(audio_path),
        "-f",
        "s16le",
        "-ac",
        "1",
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(SAMPLE_RATE),
        "-",
    ]
    process = subprocess.run(command, capture_output=True, check=False)
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", "ignore").strip().splitlines()
        raise RuntimeError(
            f"ffmpeg could not decode {audio_path.name}: {detail[-1] if detail else 'unknown error'}"
        )

    return np.frombuffer(process.stdout, np.int16).astype(np.float32) / 32768.0


def speech_windows(regions: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Slice VAD speech regions into overlapping fixed-length embedding windows."""
    windows: list[tuple[float, float]] = []
    for start, end in regions:
        duration = end - start
        if duration < MIN_WINDOW_SECONDS:
            continue
        if duration <= WINDOW_SECONDS:
            windows.append((start, end))
            continue

        cursor = start
        while cursor + WINDOW_SECONDS <= end:
            windows.append((cursor, cursor + WINDOW_SECONDS))
            cursor += HOP_SECONDS
        # Only keep a tail that reaches past the last full window. Otherwise it is
        # wholly contained in it and would double-count the end of the region.
        if end - cursor >= MIN_WINDOW_SECONDS and end > windows[-1][1]:
            windows.append((cursor, end))
    return windows


def relabel_by_first_appearance(labels: list[int]) -> list[int]:
    """Renumber cluster ids so SPEAKER_00 is whoever speaks first."""
    order: dict[int, int] = {}
    for label in labels:
        if label not in order:
            order[label] = len(order)
    return [order[label] for label in labels]


def merge_turns(windows: list[tuple[float, float]], labels: list[int]) -> list[SpeakerTurn]:
    """Collapse consecutive same-speaker windows into contiguous turns."""
    turns: list[SpeakerTurn] = []
    for (start, end), label in zip(windows, labels):
        speaker = speaker_label(label)
        if turns and turns[-1].speaker == speaker and start <= turns[-1].end + MERGE_GAP_SECONDS:
            previous = turns[-1]
            turns[-1] = SpeakerTurn(previous.start, max(previous.end, end), speaker)
        else:
            turns.append(SpeakerTurn(start, end, speaker))
    return split_overlaps(absorb_minor_speakers(absorb_slivers(turns)))


def coalesce(turns: list[SpeakerTurn]) -> list[SpeakerTurn]:
    """Join neighbouring turns that name the same speaker."""
    joined: list[SpeakerTurn] = []
    for turn in turns:
        if joined and joined[-1].speaker == turn.speaker and turn.start <= joined[-1].end + MERGE_GAP_SECONDS:
            previous = joined[-1]
            joined[-1] = SpeakerTurn(previous.start, max(previous.end, turn.end), turn.speaker)
        else:
            joined.append(turn)
    return joined


def absorb_slivers(turns: list[SpeakerTurn]) -> list[SpeakerTurn]:
    """Reassign momentary turns that interrupt one continuous speaker.

    Clustering occasionally drops a window or two of a long turn into another
    speaker, which surfaces as a phantom participant credited with a second of
    speech. A turn only counts as a slip when the *same* speaker holds the floor
    on both sides of it, so a genuine short exchange between two people is left
    alone.
    """
    current = list(turns)
    for _ in range(len(current) or 1):  # bounded: each pass strictly reduces turn count
        changed = False
        index = 1
        while index < len(current) - 1:
            stop, span = index, 0.0
            # Gather a run of consecutive brief turns totalling under the threshold,
            # so two different slivers back to back are handled as one interruption.
            while stop < len(current) - 1:
                length = current[stop].end - current[stop].start
                if length >= SLIVER_SECONDS or span + length >= SLIVER_SECONDS:
                    break
                span += length
                stop += 1

            host = current[index - 1].speaker
            if stop > index and current[stop].speaker == host and all(
                turn.speaker != host for turn in current[index:stop]
            ):
                for position in range(index, stop):
                    current[position] = replace(current[position], speaker=host)
                changed = True
            index = max(stop, index + 1)

        if not changed:
            return current
        current = coalesce(current)
    return current


def split_overlaps(turns: list[SpeakerTurn]) -> list[SpeakerTurn]:
    """Give overlapping neighbours a shared boundary at the midpoint.

    Embedding windows overlap by `HOP_SECONDS`, so a speaker change emits two
    turns that overlap by that much. Left alone, `_best_speaker` awards the whole
    overlap to the outgoing speaker, putting every change up to a hop late. The
    real change point is somewhere inside the overlap, and its midpoint is the
    unbiased estimate.
    """
    for index in range(len(turns) - 1):
        current, following = turns[index], turns[index + 1]
        if following.start < current.end:
            boundary = (following.start + current.end) / 2
            turns[index] = replace(current, end=boundary)
            turns[index + 1] = replace(following, start=boundary)
    return turns


def absorb_minor_speakers(turns: list[SpeakerTurn]) -> list[SpeakerTurn]:
    """Fold away voices too small to be participants.

    A turn's length is a poor test on its own: windows are 1.5s wide, so a
    phantom can hold a two-second turn containing a fraction of a second of
    speech. Judging a speaker by everything they are credited with across the
    whole recording catches that, and runs after `absorb_slivers` so the totals
    it sees are no longer inflated by misattributed fragments.
    """
    totals: dict[str, float] = defaultdict(float)
    for turn in turns:
        totals[turn.speaker] += max(0.0, turn.end - turn.start)

    overall = sum(totals.values())
    if overall <= 0 or len(totals) < 2:
        return turns

    minor = {
        speaker
        for speaker, total in totals.items()
        if total < MIN_SPEAKER_SECONDS and total / overall < MIN_SPEAKER_SHARE
    }
    # Never fold every voice away; something has to hold the floor.
    if not minor or len(minor) >= len(totals):
        return turns

    current = list(turns)
    for index, turn in enumerate(current):
        if turn.speaker not in minor:
            continue
        host = _nearest_major_speaker(current, index, minor)
        if host is not None:
            current[index] = replace(turn, speaker=host)
    return coalesce(current)


def _nearest_major_speaker(
    turns: list[SpeakerTurn], index: int, minor: set[str]
) -> str | None:
    """The closest surviving voice either side, preferring the one before."""
    for offset in range(1, len(turns)):
        before = index - offset
        if before >= 0 and turns[before].speaker not in minor:
            return turns[before].speaker
        after = index + offset
        if after < len(turns) and turns[after].speaker not in minor:
            return turns[after].speaker
    return None


def assign_speakers(result: dict[str, Any], turns: list[SpeakerTurn]) -> dict[str, Any]:
    """Attach a speaker to every word and segment of a Whisper result."""
    segments: list[dict[str, Any]] = []
    for segment in result.get("segments") or []:
        updated = dict(segment)
        segment_start = _number(segment.get("start"), 0.0)
        segment_end = _number(segment.get("end"), segment_start)

        words = [dict(word) for word in segment.get("words") or []]
        for word in words:
            start = _number(word.get("start"), segment_start)
            end = _number(word.get("end"), start)
            word["speaker"] = _best_speaker(start, end, turns)

        if words:
            updated["words"] = words
            updated["speaker"] = _dominant_speaker(words)
        else:
            updated["speaker"] = _best_speaker(segment_start, segment_end, turns)
        segments.append(updated)

    return {**result, "segments": segments}


def cluster_labels(
    embeddings: Any,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> list[int]:
    """Group embeddings into speakers, picking the count by silhouette score."""
    count = len(embeddings)
    if count == 0:
        return []

    from sklearn.metrics import silhouette_score

    # Both bounds clamp to the window count: asking for more speakers than there
    # are windows to cluster is a user-reachable input, not a programming error.
    low = max(1, min(min_speakers or 1, count))
    high = max(low, min(max_speakers or DEFAULT_MAX_SPEAKERS, count))
    if low == high:
        return _fit_clusters(embeddings, low)

    best_labels: list[int] | None = None
    best_score: float | None = None
    for size in range(max(low, 2), high + 1):
        labels = _fit_clusters(embeddings, size)
        if len(set(labels)) < 2:
            continue
        score = float(silhouette_score(embeddings, labels, metric="cosine"))
        if best_score is None or score > best_score:
            best_labels, best_score = labels, score

    if best_labels is None or best_score is None:
        return [0] * count
    if min_speakers is None and (
        best_score < SINGLE_SPEAKER_SILHOUETTE
        or _widest_centroid_distance(embeddings, best_labels) < MIN_SPEAKER_DISTANCE
    ):
        return [0] * count
    return best_labels


class LocalDiarizer:
    """Silero VAD + SpeechBrain ECAPA + agglomerative clustering, all on-machine."""

    def diarize(
        self,
        audio_path: Path,
        options: TranscribeOptions,
        progress: Any,
    ) -> list[SpeakerTurn]:
        progress(DECODE_PROGRESS, "Decoding audio for speaker analysis")
        waveform = load_audio_16k(audio_path)

        progress(VAD_PROGRESS, "Detecting speech regions with Silero VAD")
        regions = self._speech_regions(waveform)
        windows = speech_windows(regions)
        if not windows:
            return []

        progress(EMBEDDING_PROGRESS_START, f"Embedding {len(windows)} speech windows")
        embeddings = self._embeddings(waveform, windows, progress)

        progress(CLUSTERING_PROGRESS, "Clustering speaker embeddings")
        labels = relabel_by_first_appearance(
            cluster_labels(embeddings, options.min_speakers, options.max_speakers)
        )
        return merge_turns(windows, labels)

    def _speech_regions(self, waveform: Any) -> list[tuple[float, float]]:
        import torch
        from silero_vad import get_speech_timestamps
        from silero_vad import load_silero_vad

        model = load_silero_vad()
        # Sample indices rather than return_seconds, whose default time_resolution
        # rounds boundaries to a tenth of a second.
        stamps = get_speech_timestamps(
            torch.from_numpy(waveform),
            model,
            sampling_rate=SAMPLE_RATE,
        )
        return [
            (float(stamp["start"]) / SAMPLE_RATE, float(stamp["end"]) / SAMPLE_RATE)
            for stamp in stamps
        ]

    def _embeddings(self, waveform: Any, windows: list[tuple[float, float]], progress: Any) -> Any:
        import numpy as np
        import torch
        from speechbrain.inference.speaker import EncoderClassifier

        encoder = EncoderClassifier.from_hparams(
            source=EMBEDDING_MODEL,
            savedir=str(model_cache_dir() / "spkrec-ecapa-voxceleb"),
            run_opts={"device": "cpu"},
        )

        vectors = []
        with torch.no_grad():
            for index, (start, end) in enumerate(windows, start=1):
                chunk = waveform[int(start * SAMPLE_RATE) : int(end * SAMPLE_RATE)]
                batch = torch.from_numpy(np.ascontiguousarray(chunk)).unsqueeze(0)
                vectors.append(encoder.encode_batch(batch).reshape(-1).cpu().numpy())
                if index % EMBEDDING_PROGRESS_EVERY == 0:
                    progress(
                        _embedding_progress(index, len(windows)),
                        f"Embedding speech windows ({index}/{len(windows)})",
                    )
        return np.vstack(vectors)


def _embedding_progress(done: int, total: int) -> float:
    if total <= 0:
        return EMBEDDING_PROGRESS_END
    span = EMBEDDING_PROGRESS_END - EMBEDDING_PROGRESS_START
    return EMBEDDING_PROGRESS_START + span * min(1.0, done / total)


def _widest_centroid_distance(embeddings: Any, labels: list[int]) -> float:
    """Cosine distance between the two furthest-apart cluster centroids."""
    import numpy as np
    from sklearn.metrics.pairwise import cosine_distances

    matrix = np.asarray(embeddings, dtype=float)
    label_array = np.asarray(labels)
    centroids = np.vstack(
        [matrix[label_array == label].mean(axis=0) for label in sorted(set(labels))]
    )
    if len(centroids) < 2:
        return 0.0
    return float(cosine_distances(centroids).max())


def _fit_clusters(embeddings: Any, size: int) -> list[int]:
    from sklearn.cluster import AgglomerativeClustering

    if size <= 1:
        return [0] * len(embeddings)
    model = AgglomerativeClustering(n_clusters=size, metric="cosine", linkage="average")
    return [int(label) for label in model.fit_predict(embeddings)]


def _overlap(start: float, end: float, other_start: float, other_end: float) -> float:
    return max(0.0, min(end, other_end) - max(start, other_start))


def _distance_to_turn(point: float, turn: SpeakerTurn) -> float:
    if turn.start <= point <= turn.end:
        return 0.0
    return min(abs(point - turn.start), abs(point - turn.end))


def _best_speaker(start: float, end: float, turns: list[SpeakerTurn]) -> str:
    if not turns:
        return speaker_label(0)

    best_speaker: str | None = None
    best_overlap = 0.0
    for turn in turns:
        amount = _overlap(start, end, turn.start, turn.end)
        if amount > best_overlap:
            best_overlap, best_speaker = amount, turn.speaker
    if best_speaker is not None:
        return best_speaker

    # The word sits in a VAD gap, so fall back to the nearest turn.
    midpoint = (start + end) / 2
    return min(turns, key=lambda turn: _distance_to_turn(midpoint, turn)).speaker


def _dominant_speaker(words: list[dict[str, Any]]) -> str:
    totals: dict[str, float] = defaultdict(float)
    for word in words:
        start = _number(word.get("start"), 0.0)
        end = _number(word.get("end"), start)
        totals[str(word.get("speaker") or speaker_label(0))] += max(0.0, end - start)
    if not totals:
        return speaker_label(0)
    # Ties break on the label so the result stays deterministic.
    return max(sorted(totals), key=lambda speaker: totals[speaker])


def _number(value: Any, fallback: float) -> float:
    if value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
