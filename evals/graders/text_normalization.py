"""Text helpers the graders share: numbers, names, and whole-word matching."""

import re
from collections.abc import Iterator
from decimal import Decimal, InvalidOperation
from typing import Any

NUMBER = re.compile(
    r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?\s?"
    r"(?:%|percent|x|thousand|million|billion|mn|bn|k|m|b)?(?![\w])",
    re.IGNORECASE,
)
_SCALES = {
    "k": Decimal(1_000),
    "thousand": Decimal(1_000),
    "m": Decimal(1_000_000),
    "mn": Decimal(1_000_000),
    "million": Decimal(1_000_000),
    "b": Decimal(1_000_000_000),
    "bn": Decimal(1_000_000_000),
    "billion": Decimal(1_000_000_000),
}
_VALUE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*([a-z%]*)")
ISO_DATE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b")
COMPANY_SUFFIXES = frozenset({"inc", "llc", "ltd", "corp", "co"})
_NON_WORD_RUNS = re.compile(r"[\W_]+")


def extract_numbers(text: str, *, skip_dates: bool = True) -> list[str]:
    """Return the numbers in ``text`` as written (``$2.4M``, ``40 percent``).

    A digit run glued to a letter (``p99``, ``S3``) is not a number. ISO dates
    such as ``2019-03`` are left out unless ``skip_dates`` is False.
    """
    cleaned = ISO_DATE.sub(" ", text) if skip_dates else text
    return [match.group().strip().rstrip(",") for match in NUMBER.finditer(cleaned)]


def number_values(token: str) -> set[Decimal]:
    """Return the quantities a number as written can stand for.

    That is its value with any scale applied (``9.8k`` and ``9,800`` are both
    9800, ``$1.2M`` and ``1.2 million`` both 1,200,000) and the bare digits
    as written (9.8, 1.2), so a figure the knowledge base gives with a
    different scale word still matches. Thousands separators, ``$``, and the
    ``%`` or ``x`` unit are ignored. Empty when ``token`` has no digits.
    """
    match = _VALUE.search(token.lower())
    if match is None:
        return set()
    try:
        digits = Decimal(match.group(1).replace(",", ""))
    except InvalidOperation:
        return set()
    scale = _SCALES.get(match.group(2), Decimal(1))
    return {digits, digits * scale}


def supported_numbers(text: str) -> set[Decimal]:
    """Return every quantity the numbers in ``text`` (dates included) stand for."""
    return {
        value
        for token in extract_numbers(text, skip_dates=False)
        for value in number_values(token)
    }


def is_supported_number(token: str, supported: set[Decimal]) -> bool:
    """Return True if ``token`` (as written) states a quantity in ``supported``."""
    return bool(number_values(token) & supported)


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


COMMON_WORD_NAMES = frozenset(
    {
        "airflow",
        "amplitude",
        "apollo",
        "beam",
        "box",
        "chef",
        "chorus",
        "clarity",
        "crystal",
        "dart",
        "delta",
        "envoy",
        "falcon",
        "flume",
        "go",
        "gong",
        "gusto",
        "heap",
        "helm",
        "hive",
        "iceberg",
        "julia",
        "keystone",
        "looker",
        "mode",
        "nomad",
        "notion",
        "oracle",
        "outreach",
        "packer",
        "pig",
        "prism",
        "puppet",
        "python",
        "ruby",
        "rust",
        "sage",
        "salt",
        "sap",
        "segment",
        "sentinel",
        "sketch",
        "slack",
        "snowflake",
        "spark",
        "square",
        "storm",
        "stripe",
        "swift",
        "tableau",
        "vault",
        "workday",
        "zoom",
    }
)
"""Tool and product names that are also common English words.

A single-word forbidden claim spelled with capitals that is one of these
matches only in that exact case, so the verb in "spark interest" is not a
claim of Spark. Add a name here when a case forbids it.
"""


def claims_term(text: str, term: str) -> bool:
    """Return True if ``text`` claims the forbidden ``term``.

    The term must occur as whole words. A single-word term that is also a
    common English word (``COMMON_WORD_NAMES``) and is spelled with capitals
    must match in exact case; every other term matches in any case.
    """
    exact = (
        " " not in term.strip()
        and term.lower() in COMMON_WORD_NAMES
        and term != term.lower()
    )
    pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
    return re.search(pattern, text, 0 if exact else re.IGNORECASE) is not None


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
