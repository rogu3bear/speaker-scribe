from speaker_scribe_backend.models import TranscriptSegment
from speaker_scribe_backend.transcript import build_speakers
from speaker_scribe_backend.transcript import normalize_transcription_result
from speaker_scribe_backend.transcript import with_clean_text


def test_normalize_words_splits_on_speaker_change() -> None:
    result = {
        "segments": [
            {
                "words": [
                    {"word": "Hello", "start": 0.0, "end": 0.3, "speaker": "SPEAKER_00"},
                    {"word": "there", "start": 0.3, "end": 0.6, "speaker": "SPEAKER_00"},
                    {"word": "Hi", "start": 0.8, "end": 1.0, "speaker": "SPEAKER_01"},
                ]
            }
        ]
    }

    segments, duration = normalize_transcription_result(result)

    assert duration == 1.0
    assert [segment.speaker for segment in segments] == ["SPEAKER_00", "SPEAKER_01"]
    assert [segment.text for segment in segments] == ["Hello there", "Hi"]


def test_normalized_segments_do_not_carry_cleaned_text() -> None:
    """Cleanup is derived on read, so nothing tidied is ever written to the store."""
    segments, _ = normalize_transcription_result(
        {"segments": [{"start": 0, "end": 2, "text": "um so the the plan"}]}
    )

    assert segments[0].text == "um so the the plan"
    assert segments[0].clean_text == ""


def test_with_clean_text_derives_the_tidied_rendering() -> None:
    segments, _ = normalize_transcription_result(
        {"segments": [{"start": 0, "end": 2, "text": "um so the the plan"}]}
    )

    derived = with_clean_text(segments)

    assert derived[0].clean_text == "So the plan"
    assert derived[0].text == "um so the the plan"
    # The originals are untouched, so nothing can leak back into storage.
    assert segments[0].clean_text == ""


def test_with_clean_text_does_not_capitalize_a_continuing_fragment() -> None:
    """Joined into a paragraph, a mid-sentence capital reads as a mistake."""
    segments = [
        TranscriptSegment(id="a", start=0, end=2, text="when someone asks what the context is"),
        TranscriptSegment(id="b", start=2, end=4, text="your response is not the point."),
    ]

    derived = with_clean_text(segments)

    assert derived[0].clean_text == "When someone asks what the context is"
    assert derived[1].clean_text == "your response is not the point."


def test_with_clean_text_capitalizes_after_a_finished_sentence() -> None:
    segments = [
        TranscriptSegment(id="a", start=0, end=2, text="that is how it happens."),
        TranscriptSegment(id="b", start=2, end=4, text="your response matters."),
    ]

    assert with_clean_text(segments)[1].clean_text == "Your response matters."


def test_with_clean_text_capitalizes_when_the_speaker_changes() -> None:
    """A new speaker starts a new sentence however the last one trailed off."""
    segments = [
        TranscriptSegment(id="a", start=0, end=2, text="and then we", speaker="SPEAKER_00"),
        TranscriptSegment(id="b", start=2, end=4, text="wait, hold on", speaker="SPEAKER_01"),
    ]

    assert with_clean_text(segments)[1].clean_text == "Wait, hold on"


def test_with_clean_text_applies_to_transcripts_made_before_cleanup_existed() -> None:
    """The whole point of deriving on read: old stored jobs tidy up too."""
    legacy = [
        TranscriptSegment(id="seg-1", start=0, end=2, text="uh yeah that that works"),
    ]

    assert with_clean_text(legacy)[0].clean_text == "Yeah that works"


def test_build_speakers_accumulates_talk_time() -> None:
    segments, _ = normalize_transcription_result(
        {
            "segments": [
                {"start": 0, "end": 2, "text": "One", "speaker": "SPEAKER_00"},
                {"start": 3, "end": 5.5, "text": "Two", "speaker": "SPEAKER_00"},
                {"start": 6, "end": 7, "text": "Three", "speaker": "SPEAKER_01"},
            ]
        }
    )

    speakers = build_speakers(segments)

    assert [(speaker.id, speaker.seconds) for speaker in speakers] == [
        ("SPEAKER_00", 4.5),
        ("SPEAKER_01", 1.0),
    ]
