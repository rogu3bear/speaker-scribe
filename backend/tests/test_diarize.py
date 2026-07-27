import pytest

from speaker_scribe_backend.diarize import HOP_SECONDS
from speaker_scribe_backend.diarize import WINDOW_SECONDS
from speaker_scribe_backend.diarize import SpeakerTurn
from speaker_scribe_backend.diarize import assign_speakers
from speaker_scribe_backend.diarize import cluster_labels
from speaker_scribe_backend.diarize import merge_turns
from speaker_scribe_backend.diarize import relabel_by_first_appearance
from speaker_scribe_backend.diarize import speech_windows
from speaker_scribe_backend.pipeline import resolve_model

TWO_TURNS = [
    SpeakerTurn(start=0.0, end=5.0, speaker="SPEAKER_00"),
    SpeakerTurn(start=6.0, end=10.0, speaker="SPEAKER_01"),
]


def test_speech_windows_slices_long_region_with_overlap() -> None:
    windows = speech_windows([(0.0, 3.0)])

    assert windows[0] == (0.0, WINDOW_SECONDS)
    assert windows[1] == (HOP_SECONDS, HOP_SECONDS + WINDOW_SECONDS)
    assert all(end - start > 0 for start, end in windows)
    assert windows[-1][1] <= 3.0


def test_speech_windows_drops_regions_shorter_than_the_minimum() -> None:
    assert speech_windows([(0.0, 0.2)]) == []


def test_speech_windows_keeps_a_short_region_whole() -> None:
    assert speech_windows([(1.0, 2.0)]) == [(1.0, 2.0)]


def test_relabel_by_first_appearance_renumbers_from_zero() -> None:
    assert relabel_by_first_appearance([3, 3, 1, 1, 3, 7]) == [0, 0, 1, 1, 0, 2]


def test_merge_turns_collapses_consecutive_same_speaker_windows() -> None:
    windows = [(0.0, 1.5), (0.75, 2.25), (5.0, 6.5)]

    turns = merge_turns(windows, [0, 0, 1])

    assert turns == [
        SpeakerTurn(start=0.0, end=2.25, speaker="SPEAKER_00"),
        SpeakerTurn(start=5.0, end=6.5, speaker="SPEAKER_01"),
    ]


def test_merge_turns_splits_when_the_speaker_changes_back() -> None:
    turns = merge_turns([(0.0, 1.5), (1.5, 3.0), (3.0, 4.5)], [0, 1, 0])

    assert [turn.speaker for turn in turns] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"]


def test_assign_speakers_maps_words_by_maximum_overlap() -> None:
    result = {
        "segments": [
            {
                "start": 0.0,
                "end": 8.0,
                "text": "Hello there hi",
                "words": [
                    {"word": "Hello", "start": 0.0, "end": 0.5},
                    {"word": "there", "start": 0.6, "end": 1.2},
                    {"word": "hi", "start": 6.2, "end": 6.8},
                ],
            }
        ]
    }

    assigned = assign_speakers(result, TWO_TURNS)
    words = assigned["segments"][0]["words"]

    assert [word["speaker"] for word in words] == [
        "SPEAKER_00",
        "SPEAKER_00",
        "SPEAKER_01",
    ]


def test_assign_speakers_labels_the_segment_with_its_dominant_speaker() -> None:
    result = {
        "segments": [
            {
                "start": 0.0,
                "end": 8.0,
                "words": [
                    {"word": "Hello", "start": 0.0, "end": 3.0},
                    {"word": "hi", "start": 6.2, "end": 6.8},
                ],
            }
        ]
    }

    assigned = assign_speakers(result, TWO_TURNS)

    assert assigned["segments"][0]["speaker"] == "SPEAKER_00"


def test_assign_speakers_falls_back_to_the_nearest_turn_inside_a_vad_gap() -> None:
    """A word can land in silence that the VAD dropped, so it overlaps nothing."""
    # The gap runs 5.0-6.0; this word sits in it but nearer the second turn.
    result = {
        "segments": [
            {"start": 5.6, "end": 5.8, "words": [{"word": "um", "start": 5.6, "end": 5.8}]}
        ]
    }

    assigned = assign_speakers(result, TWO_TURNS)

    assert assigned["segments"][0]["words"][0]["speaker"] == "SPEAKER_01"


def test_assign_speakers_handles_segments_without_word_timestamps() -> None:
    result = {"segments": [{"start": 6.5, "end": 9.0, "text": "no words here"}]}

    assigned = assign_speakers(result, TWO_TURNS)

    assert assigned["segments"][0]["speaker"] == "SPEAKER_01"


def test_assign_speakers_defaults_to_one_speaker_when_diarization_found_nothing() -> None:
    result = {"segments": [{"start": 0.0, "end": 1.0, "text": "alone"}]}

    assigned = assign_speakers(result, [])

    assert assigned["segments"][0]["speaker"] == "SPEAKER_00"


def test_assign_speakers_does_not_mutate_the_input() -> None:
    result = {"segments": [{"start": 0.0, "end": 1.0, "words": [{"word": "x", "start": 0.0, "end": 1.0}]}]}

    assign_speakers(result, TWO_TURNS)

    assert "speaker" not in result["segments"][0]
    assert "speaker" not in result["segments"][0]["words"][0]


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("large-v3", "mlx-community/whisper-large-v3-mlx"),
        ("small", "mlx-community/whisper-small-mlx"),
        ("mlx-community/whisper-large-v3-turbo", "mlx-community/whisper-large-v3-turbo"),
    ],
)
def test_resolve_model_maps_short_names_to_mlx_repos(model: str, expected: str) -> None:
    assert resolve_model(model) == expected


def two_voice_embeddings() -> list[list[float]]:
    """Two tight, near-orthogonal clusters — an easy two-speaker case."""
    first = [[1.0, 0.0, 0.02 * index] for index in range(5)]
    second = [[0.0, 1.0, 0.02 * index] for index in range(5)]
    return first + second


def test_cluster_labels_separates_two_distinct_voices() -> None:
    pytest.importorskip("sklearn")

    labels = cluster_labels(two_voice_embeddings())

    assert len(set(labels)) == 2
    assert len(set(labels[:5])) == 1
    assert len(set(labels[5:])) == 1
    assert labels[0] != labels[5]


def test_cluster_labels_honours_an_explicit_speaker_count() -> None:
    pytest.importorskip("sklearn")

    labels = cluster_labels(two_voice_embeddings(), min_speakers=3, max_speakers=3)

    assert len(set(labels)) == 3


def test_cluster_labels_reports_one_speaker_for_a_uniform_recording() -> None:
    pytest.importorskip("sklearn")

    embeddings = [[1.0, 0.001 * index, 0.0] for index in range(10)]

    assert set(cluster_labels(embeddings)) == {0}


def test_cluster_labels_returns_nothing_for_no_embeddings() -> None:
    assert cluster_labels([]) == []
