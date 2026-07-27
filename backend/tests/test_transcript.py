from speaker_scribe_backend.transcript import build_speakers
from speaker_scribe_backend.transcript import normalize_transcription_result


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
