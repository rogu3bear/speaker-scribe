import pytest

from speaker_scribe_backend.diarize import HOP_SECONDS
from speaker_scribe_backend.diarize import WINDOW_SECONDS
from speaker_scribe_backend.diarize import SpeakerTurn
from speaker_scribe_backend.diarize import absorb_minor_speakers
from speaker_scribe_backend.diarize import absorb_slivers
from speaker_scribe_backend.diarize import assign_speakers
from speaker_scribe_backend.diarize import speaker_label
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


def test_speech_windows_drops_a_tail_already_covered_by_the_last_window() -> None:
    """A tail wholly inside the previous window would double-count that audio."""
    windows = speech_windows([(0.0, 3.0)])

    assert windows == [(0.0, 1.5), (0.75, 2.25), (1.5, 3.0)]
    assert not any(
        earlier[0] <= later[0] and later[1] <= earlier[1]
        for index, earlier in enumerate(windows)
        for later in windows[index + 1 :]
    )


def test_speech_windows_keeps_a_tail_that_extends_past_the_last_window() -> None:
    assert speech_windows([(0.0, 3.4)])[-1] == (2.25, 3.4)


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
    # Each block runs well past SLIVER_SECONDS, so this is a real exchange rather
    # than a momentary slip.
    windows = [(0.0, 3.0), (3.0, 6.0), (6.0, 9.0)]

    turns = merge_turns(windows, [0, 1, 0])

    assert [turn.speaker for turn in turns] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"]


def test_merge_turns_splits_an_overlap_at_its_midpoint() -> None:
    """Windows overlap by a hop, so a speaker change emits overlapping turns."""
    windows = [(0.0, 1.5), (0.75, 2.25), (1.5, 3.0), (2.25, 3.75)]

    turns = merge_turns(windows, [0, 0, 0, 1])

    assert turns == [
        SpeakerTurn(start=0.0, end=2.625, speaker="SPEAKER_00"),
        SpeakerTurn(start=2.625, end=3.75, speaker="SPEAKER_01"),
    ]


def test_merge_turns_never_returns_overlapping_turns() -> None:
    turns = merge_turns(
        [(0.0, 1.5), (0.75, 2.25), (1.5, 3.0), (2.25, 3.75), (3.0, 4.5)],
        [0, 0, 1, 1, 0],
    )

    assert all(a.end <= b.start for a, b in zip(turns, turns[1:]))


def test_assign_speakers_does_not_lag_a_speaker_change(  # noqa: D401
) -> None:
    """Words after the boundary belong to the incoming speaker, not the outgoing one.

    Before overlaps were split, the outgoing turn won the whole overlap region and
    every change landed up to a hop late.
    """
    turns = merge_turns([(0.0, 1.5), (0.75, 2.25), (1.5, 3.0), (2.25, 3.75)], [0, 0, 0, 1])
    result = {
        "segments": [
            {
                "start": 2.0,
                "end": 3.0,
                "words": [
                    {"word": "before", "start": 2.3, "end": 2.5},
                    {"word": "after", "start": 2.7, "end": 2.9},
                ],
            }
        ]
    }

    words = assign_speakers(result, turns)["segments"][0]["words"]

    assert [word["speaker"] for word in words] == ["SPEAKER_00", "SPEAKER_01"]


def turn(start: float, end: float, label: int) -> SpeakerTurn:
    return SpeakerTurn(start=start, end=end, speaker=speaker_label(label))


def test_absorb_slivers_reassigns_a_momentary_interruption() -> None:
    """A one-second turn inside one speaker's floor is a slip, not a participant."""
    turns = absorb_slivers([turn(0, 30, 0), turn(30, 30.8, 1), turn(30.8, 60, 0)])

    assert turns == [SpeakerTurn(start=0, end=60, speaker="SPEAKER_00")]


def test_absorb_slivers_keeps_a_genuine_short_exchange() -> None:
    """Different speakers either side means the floor really did change hands."""
    turns = absorb_slivers([turn(0, 30, 0), turn(30, 31, 1), turn(31, 60, 2)])

    assert [item.speaker for item in turns] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"]


def test_absorb_slivers_keeps_a_substantial_turn() -> None:
    """The audience question that motivated this rule must survive it."""
    turns = absorb_slivers([turn(0, 30, 0), turn(30, 50, 1), turn(50, 80, 0)])

    assert [item.speaker for item in turns] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"]


def test_absorb_slivers_removes_a_phantom_speaker_entirely() -> None:
    """A voice made only of slivers should not appear in the transcript at all."""
    turns = absorb_slivers(
        [
            turn(0, 20, 0),
            turn(20, 20.4, 3),
            turn(20.4, 40, 0),
            turn(40, 40.6, 3),
            turn(40.6, 60, 0),
        ]
    )

    assert {item.speaker for item in turns} == {"SPEAKER_00"}


def test_absorb_slivers_handles_consecutive_slivers() -> None:
    turns = absorb_slivers(
        [turn(0, 20, 0), turn(20, 20.5, 1), turn(20.5, 21.2, 2), turn(21.2, 40, 0)]
    )

    assert {item.speaker for item in turns} == {"SPEAKER_00"}


def test_absorb_slivers_leaves_the_edges_alone() -> None:
    """A short first or last turn has no speaker on both sides, so it stands."""
    turns = absorb_slivers([turn(0, 0.5, 1), turn(0.5, 30, 0), turn(30, 30.5, 2)])

    assert [item.speaker for item in turns] == ["SPEAKER_01", "SPEAKER_00", "SPEAKER_02"]


def test_absorb_slivers_is_a_no_op_on_short_input() -> None:
    assert absorb_slivers([]) == []
    assert absorb_slivers([turn(0, 1, 0)]) == [turn(0, 1, 0)]
    assert absorb_slivers([turn(0, 1, 0), turn(1, 2, 1)]) == [turn(0, 1, 0), turn(1, 2, 1)]


def test_merge_turns_drops_a_sliver_end_to_end() -> None:
    windows = [(0.0, 1.5), (0.75, 2.25), (1.5, 3.0), (2.25, 3.75), (3.0, 4.5), (3.75, 5.25)]

    turns = merge_turns(windows, [0, 0, 0, 1, 0, 0])

    assert {item.speaker for item in turns} == {"SPEAKER_00"}


def test_absorb_minor_speakers_folds_a_phantom_with_a_long_but_empty_turn() -> None:
    """A turn can clear the sliver threshold while its speaker is still a ghost.

    Windows are 1.5s wide, so clustering can hand a phantom a 2.5s turn holding a
    fraction of a second of speech. Total credit across the recording catches it.
    """
    turns = [
        turn(0, 600, 0),
        turn(600, 602.5, 3),
        turn(602.5, 1200, 0),
        turn(1200, 1400, 2),
    ]

    folded = absorb_minor_speakers(turns)

    assert {item.speaker for item in folded} == {"SPEAKER_00", "SPEAKER_02"}


def test_absorb_minor_speakers_keeps_a_brief_but_real_contributor() -> None:
    """The audience question this rule must not eat: one turn, twenty seconds."""
    turns = [turn(0, 600, 0), turn(600, 620, 1), turn(620, 1200, 2)]

    folded = absorb_minor_speakers(turns)

    assert [item.speaker for item in folded] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"]


def test_absorb_minor_speakers_protects_short_recordings_by_share() -> None:
    """Four seconds is most of a ninety-second clip, so it is not a phantom."""
    turns = [turn(0, 40, 0), turn(40, 44, 1), turn(44, 90, 0)]

    folded = absorb_minor_speakers(turns)

    assert {item.speaker for item in folded} == {"SPEAKER_00", "SPEAKER_01"}


def test_absorb_minor_speakers_never_folds_every_voice() -> None:
    turns = [turn(0, 1, 0), turn(1, 2, 1)]

    assert absorb_minor_speakers(turns) == turns


def test_absorb_minor_speakers_leaves_a_single_speaker_alone() -> None:
    turns = [turn(0, 2, 0)]

    assert absorb_minor_speakers(turns) == turns


def test_absorb_minor_speakers_is_a_no_op_when_every_voice_is_substantial() -> None:
    turns = [turn(0, 300, 0), turn(300, 600, 1), turn(600, 900, 2)]

    assert absorb_minor_speakers(turns) == turns


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


def test_cluster_labels_clamps_a_speaker_floor_above_the_window_count() -> None:
    """min_speakers is user input, so it can exceed the windows available.

    Short audio yields very few embedding windows; asking for more speakers than
    that used to reach AgglomerativeClustering with n_clusters > n_samples and
    raise ValueError after transcription had already completed.
    """
    pytest.importorskip("sklearn")

    assert cluster_labels([[1.0, 0.0, 0.0]], min_speakers=4) == [0]
    assert cluster_labels([[1.0, 0.0, 0.0]], min_speakers=12, max_speakers=12) == [0]
    assert len(set(cluster_labels(two_voice_embeddings(), min_speakers=12))) <= 10
