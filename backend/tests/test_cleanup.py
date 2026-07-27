import pytest

from speaker_scribe_backend.cleanup import clean_text
from speaker_scribe_backend.cleanup import is_sentence_end


@pytest.mark.parametrize(
    ("verbatim", "expected"),
    [
        ("um so I was thinking", "So I was thinking"),
        ("So, uh, I was thinking", "So, I was thinking"),
        ("hmm mm yeah", "Yeah"),
        ("I was, you know, thinking", "I was, you know, thinking"),
    ],
)
def test_clean_text_removes_standalone_hesitations(verbatim: str, expected: str) -> None:
    assert clean_text(verbatim) == expected


def test_clean_text_keeps_filler_lookalikes_inside_real_words() -> None:
    assert clean_text("the umbrella was ahead of us") == "The umbrella was ahead of us"


def test_clean_text_collapses_an_immediately_repeated_word() -> None:
    assert clean_text("this is is the the plan") == "This is the plan"


def test_clean_text_keeps_a_legitimate_repeat_across_punctuation() -> None:
    assert clean_text("no, no I disagree") == "No, no I disagree"


def test_clean_text_drops_a_false_start_the_next_word_completes() -> None:
    assert clean_text("wh- what do you mean") == "What do you mean"


def test_clean_text_keeps_a_dangling_word_that_is_not_a_false_start() -> None:
    assert clean_text("the co- operative model") == "The co- operative model"


def test_clean_text_drops_a_leading_discourse_marker() -> None:
    assert clean_text("you know, it depends") == "It depends"
    assert clean_text("I mean it depends") == "It depends"


def test_clean_text_keeps_the_same_phrase_when_it_carries_meaning() -> None:
    assert clean_text("do you know what I mean") == "Do you know what I mean"


def test_clean_text_keeps_punctuation_tight() -> None:
    assert clean_text("well , that's fine .") == "Well, that's fine."


def test_clean_text_capitalizes_the_opening_word() -> None:
    assert clean_text("okay so clarifying the understanding") == (
        "Okay so clarifying the understanding"
    )


@pytest.mark.parametrize(
    ("verbatim", "expected"),
    [
        ("we save you $100,000.", "We save you $100,000."),
        ("about 3.5 percent", "About 3.5 percent"),
        ("that's 1,250 users", "That's 1,250 users"),
        ("roughly 40% of them", "Roughly 40% of them"),
    ],
)
def test_clean_text_keeps_numbers_and_currency_intact(verbatim: str, expected: str) -> None:
    assert clean_text(verbatim) == expected


def test_clean_text_leaves_a_continuing_fragment_lowercase() -> None:
    """Whisper splits mid-sentence; capitalizing every split breaks the paragraph."""
    assert clean_text("your response is not the point", starts_sentence=False) == (
        "your response is not the point"
    )
    assert clean_text("your response is not the point") == "Your response is not the point"


def test_clean_text_returns_empty_for_pure_filler() -> None:
    assert clean_text("um uh hmm") == ""
    assert clean_text("") == ""
    assert clean_text("   ") == ""


def test_clean_text_never_invents_content() -> None:
    """Cleanup only removes and reformats; it must not add words."""
    verbatim = "um so the the thing is, uh, it works"
    cleaned = clean_text(verbatim)

    original_words = {word.lower().strip(",.") for word in verbatim.split()}
    for word in cleaned.split():
        assert word.lower().strip(",.") in original_words


@pytest.mark.parametrize(
    ("text", "expected"),
    [("It works.", True), ("Does it?", True), ("Stop!", True), ("and then", False)],
)
def test_is_sentence_end_detects_terminal_punctuation(text: str, expected: bool) -> None:
    assert is_sentence_end(text) is expected
