"""Text helpers the graders share: numbers, names, and whole-word matching."""

import re
from collections.abc import Iterator
from typing import Any

NUMBER = re.compile(
    r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?\s?(?:%|percent|x|k|m|b)?(?![\w])",
    re.IGNORECASE,
)
ISO_DATE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b")
NUMBER_UNITS = "%xkmb"
COMPANY_SUFFIXES = frozenset({"inc", "llc", "ltd", "corp", "co"})
_NON_WORD_RUNS = re.compile(r"[\W_]+")


def extract_numbers(text: str, *, skip_dates: bool = True) -> list[str]:
    """Return the numbers in ``text`` as written (``$2.4M``, ``40 percent``).

    A digit run glued to a letter (``p99``, ``S3``) is not a number. ISO dates
    such as ``2019-03`` are left out unless ``skip_dates`` is False.
    """
    cleaned = ISO_DATE.sub(" ", text) if skip_dates else text
    return [match.group().strip().rstrip(",") for match in NUMBER.finditer(cleaned)]


def normalize_number(raw: str) -> str:
    """Return ``raw`` without ``$``, commas, or spaces, lowercase, with ``%``."""
    squeezed = re.sub(r"\s+", "", raw.lower())
    return squeezed.replace("$", "").replace(",", "").replace("percent", "%")


def bare_digits(normalized: str) -> str:
    """Return a normalized number without its unit (``2.4m`` becomes ``2.4``)."""
    return normalized.rstrip(NUMBER_UNITS)


def supported_numbers(text: str) -> set[str]:
    """Return the numbers in ``text`` (dates included), with and without units."""
    normalized = {
        normalize_number(token) for token in extract_numbers(text, skip_dates=False)
    }
    return normalized | {bare_digits(number) for number in normalized}


def is_supported_number(token: str, supported: set[str]) -> bool:
    """Return True if ``token`` (as written) is among ``supported`` numbers."""
    normalized = normalize_number(token)
    return normalized in supported or bare_digits(normalized) in supported


def normalize_text(text: str) -> str:
    """Lowercase ``text`` and reduce every run of punctuation to one space."""
    return _NON_WORD_RUNS.sub(" ", text.lower()).strip()


def normalize_company(name: str) -> str:
    """Normalize a company or title, dropping trailing ``Inc``, ``LLC``, ``Co``..."""
    words = normalize_text(name).split()
    while words and words[-1] in COMPANY_SUFFIXES:
        words.pop()
    return " ".join(words)


def contains_phrase(normalized_text: str, normalized_phrase: str) -> bool:
    """Return True if the phrase occurs in the text as whole words."""
    return f" {normalized_phrase} " in f" {normalized_text} "


def contains_term(text: str, term: str) -> bool:
    """Return True if ``term`` occurs in ``text`` as a whole word, any case."""
    pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
    return re.search(pattern, text, re.IGNORECASE) is not None


def iter_strings(value: Any) -> Iterator[str]:
    """Yield every string inside nested mappings and lists, keys excluded."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)


def iter_mappings(value: Any) -> Iterator[dict[str, Any]]:
    """Yield every mapping inside nested mappings and lists, outermost first."""
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from iter_mappings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_mappings(item)
