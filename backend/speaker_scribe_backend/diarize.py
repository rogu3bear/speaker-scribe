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
EMBEDDING_PROGRESS_EVERY = 64
EMBEDDING_PROGRESS_START = 0.62
EMBEDDING_PROGRESS_END = 0.80


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
    return split_overlaps(turns)


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
        waveform = load_audio_16k(audio_path)

        progress(0.55, "Detecting speech regions with Silero VAD")
        regions = self._speech_regions(waveform)
        windows = speech_windows(regions)
        if not windows:
            return []

        progress(0.62, f"Embedding {len(windows)} speech windows")
        embeddings = self._embeddings(waveform, windows, progress)

        progress(0.82, "Clustering speaker embeddings")
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
