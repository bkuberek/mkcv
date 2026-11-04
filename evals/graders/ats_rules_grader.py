"""Does the resume YAML follow the rules applicant tracking systems need?"""

import re
from collections.abc import Callable
from typing import Any

from evals.graders.grading_context import GradingContext
from evals.graders.resume_yaml import load_cv, structure_problems
from evals.graders.text_normalization import iter_mappings, iter_strings
from evals.models.grade import Grade

STANDARD_HEADINGS = frozenset(
    {
        "summary",
        "experience",
        "work experience",
        "professional experience",
        "earlier experience",
        "education",
        "skills",
        "technical skills",
        "technologies",
        "projects",
        "certifications",
        "publications",
        "languages",
        "awards",
        "volunteer",
        "volunteering",
    }
)
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FIRST_PERSON = re.compile(r"(?i)\b(i|me|my|mine|myself)\b")
YEAR_MONTH = re.compile(r"^\d{4}(-\d{2})?$")
HTML_TAG = re.compile(r"<[A-Za-z]")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
MAX_HIGHLIGHT_CHARS = 300
MIN_HIGHLIGHTS = 1
MAX_HIGHLIGHTS = 8

_Rule = Callable[[dict[str, Any]], list[str]]


def _highlights(cv: dict[str, Any]) -> list[str]:
    sections = cv.get("sections", {})
    return [
        str(item)
        for entry in iter_mappings(sections)
        if isinstance(entry.get("highlights"), list)
        for item in entry["highlights"]
    ]


def _nonstandard_headings(cv: dict[str, Any]) -> list[str]:
    sections = cv.get("sections", {})
    return [
        str(key)
        for key in sections
        if str(key).lower().replace("_", " ").strip() not in STANDARD_HEADINGS
    ]


def _malformed_email(cv: dict[str, Any]) -> list[str]:
    email = cv.get("email")
    if isinstance(email, str) and EMAIL.match(email):
        return []
    return [email if isinstance(email, str) else ""]


def _first_person_bullets(cv: dict[str, Any]) -> list[str]:
    return [text for text in _highlights(cv) if FIRST_PERSON.search(text)]


def _overlong_bullets(cv: dict[str, Any]) -> list[str]:
    return [text for text in _highlights(cv) if len(text) > MAX_HIGHLIGHT_CHARS]


def _highlight_counts(cv: dict[str, Any]) -> list[str]:
    offending: list[str] = []
    for entry in iter_mappings(cv.get("sections", {})):
        highlights = entry.get("highlights")
        if isinstance(highlights, list) and not (
            MIN_HIGHLIGHTS <= len(highlights) <= MAX_HIGHLIGHTS
        ):
            label = entry.get("company") or entry.get("name") or "entry"
            offending.append(f"{label}: {len(highlights)} highlights")
    return offending


def _malformed_dates(cv: dict[str, Any]) -> list[str]:
    offending: list[str] = []
    for entry in iter_mappings(cv.get("sections", {})):
        for key in ("start_date", "end_date"):
            value = entry.get(key)
            if value is None:
                continue
            text = str(value)
            if not YEAR_MONTH.match(text) and text.lower() != "present":
                offending.append(text)
    return offending


def _markup(cv: dict[str, Any]) -> list[str]:
    return [
        text
        for text in iter_strings(cv)
        if HTML_TAG.search(text) or TABLE_ROW.search(text)
    ]


RULES: tuple[tuple[str, _Rule], ...] = (
    ("R1", _nonstandard_headings),
    ("R2", _malformed_email),
    ("R3", _first_person_bullets),
    ("R4", _overlong_bullets),
    ("R5", _highlight_counts),
    ("R6", _malformed_dates),
    ("R7", _markup),
)
"""Rule IDs with the check that returns each rule's offending texts (design 9.6)."""


class AtsRulesGrader:
    """Checks the seven ATS rules; the score is the share of rules that hold.

    R1 standard section headings, R2 a well-formed email, R3 no first-person
    pronouns in bullets, R4 bullets of at most 300 characters, R5 one to eight
    bullets per entry, R6 dates as ``YYYY`` or ``YYYY-MM`` (or ``present``),
    R7 no HTML tags or Markdown table rows. ``details["failures"]`` lists each
    offending text with its rule ID.
    """

    name = "ats_rules"

    async def grade(self, ctx: GradingContext) -> Grade:
        """Score a stage 4 resume; 0.0 when it cannot be read as a resume."""
        try:
            cv = _readable_resume(ctx.output)
        except ValueError as error:
            return Grade(
                name=self.name,
                score=0.0,
                passed=False,
                details={"failures": [{"rule": "parse", "text": str(error)}]},
            )
        failures = [
            {"rule": rule, "text": text} for rule, check in RULES for text in check(cv)
        ]
        failed_rules = {failure["rule"] for failure in failures}
        return Grade(
            name=self.name,
            score=(len(RULES) - len(failed_rules)) / len(RULES),
            passed=not failed_rules,
            details={"failures": failures},
        )


def _readable_resume(output: dict[str, Any] | str | None) -> dict[str, Any]:
    """Return the ``cv`` mapping, or raise ValueError saying why there is none."""
    if not isinstance(output, str):
        raise ValueError("the stage produced no YAML text")
    cv = load_cv(output)
    problems = structure_problems(cv)
    if problems:
        raise ValueError("; ".join(problems))
    return cv
