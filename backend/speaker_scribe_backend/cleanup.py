"""Readability cleanup for transcript text.

Verbatim speech reads badly: filler words, stutters, repeated words across a
breath, and sentences that trail off mid-thought. This module produces a tidied
version of a segment's text.

It is deliberately non-destructive. The verbatim text is what the speaker
actually said, and for an interview that is the record — altering it in place
would silently rewrite a quote. Cleanup is stored alongside the original as a
separate field so the UI can offer it as a view and the user can always get back
to what was really said.

Everything here is deterministic and rule-based. Grammar repair and completing a
half-finished sentence need a language model; see docs/design for that path.
"""

from __future__ import annotations

import re

# Standalone hesitation sounds. Only ever removed as whole words, so "um" inside
# "umbrella" and the name "Ah" mid-sentence are untouched.
FILLER_WORDS = frozenset(
    {
        "um",
        "umm",
        "uh",
        "uhh",
        "erm",
        "er",
        "ah",
        "eh",
        "hmm",
        "hm",
        "mm",
        "mhm",
        "uh-huh",
        "mm-hmm",
    }
)

# Discourse markers that add nothing when they open a clause. Removed only in
# that position, because "you know what I mean" and "like a coding perspective"
# are load-bearing.
LEADING_FILLER_PHRASES = (
    "you know",
    "i mean",
    "sort of",
    "kind of",
)

# A trailing hyphen is part of the word, so "wh-" survives tokenization as one
# token and can be recognized as a false start.
WORD_PATTERN = re.compile(r"[A-Za-z0-9']+(?:-[A-Za-z0-9']+)*-?|[^\sA-Za-z0-9]")
SENTENCE_END = re.compile(r"[.!?]$")

SEPARATORS = frozenset({",", ";", ":"})
TERMINATORS = frozenset({".", "!", "?"})


def clean_text(text: str) -> str:
    """Tidy one segment of verbatim speech for reading."""
    tokens = WORD_PATTERN.findall(text or "")
    if not tokens:
        return ""

    kept = _drop_fillers(tokens)
    kept = _collapse_stutters(kept)
    kept = _collapse_repeats(kept)
    kept = _drop_leading_phrases(kept)
    kept = _tidy_punctuation(kept)
    if not kept:
        return ""

    rendered = _render(kept)
    return _capitalize(rendered)


def is_sentence_end(text: str) -> bool:
    """Whether text closes on terminal punctuation."""
    return bool(SENTENCE_END.search(text.strip()))


def _is_word(token: str) -> bool:
    return bool(token) and token[0].isalnum()


def _normal(token: str) -> str:
    return token.lower().strip("'")


def _drop_fillers(tokens: list[str]) -> list[str]:
    return [token for token in tokens if not (_is_word(token) and _normal(token) in FILLER_WORDS)]


def _collapse_stutters(tokens: list[str]) -> list[str]:
    """Drop a false start that the next word completes, as in 'wh- what'."""
    kept: list[str] = []
    for index, token in enumerate(tokens):
        if not _is_word(token) or not token.endswith("-"):
            kept.append(token)
            continue
        following = next((item for item in tokens[index + 1 :] if _is_word(item)), None)
        if following and _normal(following).startswith(_normal(token).rstrip("-")):
            continue
        kept.append(token)
    return kept


def _collapse_repeats(tokens: list[str]) -> list[str]:
    """Collapse an immediately repeated word, as in 'the the'.

    Only across a direct adjacency. Punctuation between them means the repeat is
    deliberate, as in "no, no I disagree".
    """
    kept: list[str] = []
    for token in tokens:
        previous = kept[-1] if kept else None
        if (
            _is_word(token)
            and previous is not None
            and _is_word(previous)
            and _normal(previous) == _normal(token)
        ):
            continue
        kept.append(token)
    return kept


def _tidy_punctuation(tokens: list[str]) -> list[str]:
    """Drop separators stranded by a removed word, as in 'So, uh, I' -> 'So, I'."""
    kept: list[str] = []
    for token in tokens:
        if token in SEPARATORS and (
            not kept or kept[-1] in SEPARATORS or kept[-1] in TERMINATORS
        ):
            continue
        kept.append(token)
    while kept and kept[-1] in SEPARATORS:
        kept.pop()
    return kept


def _drop_leading_phrases(tokens: list[str]) -> list[str]:
    lowered = [_normal(token) for token in tokens]
    for phrase in LEADING_FILLER_PHRASES:
        words = phrase.split()
        if lowered[: len(words)] == words:
            trimmed = tokens[len(words) :]
            # Drop the comma the phrase was leaning on, not the next real word.
            if trimmed and trimmed[0] == ",":
                trimmed = trimmed[1:]
            return trimmed
    return tokens


def _render(tokens: list[str]) -> str:
    out = ""
    for token in tokens:
        if not out:
            out = token
        elif token in {",", ".", "!", "?", ":", ";", "%", ")", "]", "}"}:
            out += token
        elif out[-1] in {"(", "[", "{"}:
            out += token
        elif token == "'" or token.startswith("'"):
            out += token
        else:
            out += " " + token
    return out.strip()


def _capitalize(text: str) -> str:
    if not text:
        return ""
    return text[0].upper() + text[1:]
