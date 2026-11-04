"""Does the cover letter have the shape and the names a sendable letter needs?"""

import re

from evals.graders.cover_letter_text import (
    expected_company,
    expected_role,
    letter_text,
    load_letter,
    paragraphs,
    word_count,
)
from evals.graders.grading_context import GradingContext
from evals.graders.text_normalization import (
    contains_phrase,
    normalize_company,
    normalize_text,
)
from evals.models.grade import Grade
from mkcv.core.models.cover_letter import CoverLetter

FIRST_PERSON_PLURAL = re.compile(r"\b(?:[Ww]e|us|[Oo]urs?|[Oo]urselves)\b")
PLACEHOLDER = re.compile(
    r"\[[^\]]*\]|\{[^}]*\}|<[^>]+>|\b(?:TODO|TBD|XXX)\b|(?i:lorem ipsum)"
    r"|(?i:\binsert\b[^.]{0,40}\bhere\b)"
)
MIN_BODY_PARAGRAPHS = 1
MAX_BODY_PARAGRAPHS = 3


class CoverLetterRulesGrader:
    """Seven pass/fail rules for a generated cover letter.

    - C1 the paragraphs hold between the case's ``min_words`` and
      ``max_words`` words (250 to 400 by default, as the prompt asks).
    - C2 there are one to three body paragraphs.
    - C3 no first-person plural (``we``, ``our``, ``us``) in the paragraphs.
    - C4 no placeholder text (``[Company]``, ``{name}``, ``TODO``, ...) anywhere.
    - C5 the company the JD names is the letter's company and appears in
      the paragraphs.
    - C6 the role the JD names is the letter's role title.
    - C7 the candidate's name appears in the knowledge base.

    C5 and C6 are checked only when the case or its reference analysis names
    the company and role. The score is the share of checked rules passed.
    """

    name = "cover_letter_rules"

    async def grade(self, ctx: GradingContext) -> Grade:
        """Check ``ctx.output`` against the rules."""
        try:
            letter = load_letter(ctx.output)
        except ValueError as error:
            return Grade(
                name=self.name,
                score=0.0,
                passed=False,
                details={"failures": [], "checked": [], "error": str(error)},
            )

        results = _check(letter, ctx)
        failures = [
            {"rule": rule, "text": problem}
            for rule, problem in results.items()
            if problem is not None
        ]
        return Grade(
            name=self.name,
            score=(len(results) - len(failures)) / len(results),
            passed=not failures,
            details={
                "failures": failures,
                "checked": list(results),
                "words": word_count(letter),
            },
        )


def _check(letter: CoverLetter, ctx: GradingContext) -> dict[str, str | None]:
    """Each checked rule mapped to its problem, or None when it passed."""
    bounds = ctx.case.cover_letter
    words = word_count(letter)
    body = len(letter.body_paragraphs)
    results: dict[str, str | None] = {
        "C1": (
            None
            if bounds.min_words <= words <= bounds.max_words
            else f"{words} words (want {bounds.min_words}-{bounds.max_words})"
        ),
        "C2": (
            None
            if MIN_BODY_PARAGRAPHS <= body <= MAX_BODY_PARAGRAPHS
            else f"{body} body paragraphs"
        ),
        "C3": _first_match(FIRST_PERSON_PLURAL, paragraphs(letter)),
        "C4": _first_match(PLACEHOLDER, _every_field(letter)),
    }
    company = expected_company(ctx)
    if company is not None:
        results["C5"] = _company_problem(letter, company)
    role = expected_role(ctx)
    if role is not None:
        results["C6"] = _role_problem(letter, role)
    results["C7"] = (
        None
        if contains_phrase(
            normalize_text(ctx.kb_text), normalize_text(letter.candidate_name)
        )
        else letter.candidate_name
    )
    return results


def _every_field(letter: CoverLetter) -> list[str]:
    return [
        letter.company,
        letter.role_title,
        letter.salutation,
        *paragraphs(letter),
        letter.sign_off,
        letter.candidate_name,
    ]


def _first_match(pattern: re.Pattern[str], texts: list[str]) -> str | None:
    for text in texts:
        match = pattern.search(text)
        if match:
            return match.group()
    return None


def _company_problem(letter: CoverLetter, company: str) -> str | None:
    wanted = normalize_company(company)
    named = normalize_company(letter.company)
    if not (
        contains_phrase(named, wanted) or (named and contains_phrase(wanted, named))
    ):
        return f"names {letter.company!r}, not {company!r}"
    if not contains_phrase(normalize_text(letter_text(letter)), wanted):
        return f"the paragraphs never name {company!r}"
    return None


def _role_problem(letter: CoverLetter, role: str) -> str | None:
    wanted = normalize_text(role)
    named = normalize_text(letter.role_title)
    if contains_phrase(named, wanted) or (named and contains_phrase(wanted, named)):
        return None
    return f"names {letter.role_title!r}, not {role!r}"
