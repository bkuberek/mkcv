"""Read a cover letter output the way the cover letter graders need it."""

import re
from typing import Any

from pydantic import ValidationError

from evals.graders.grading_context import GradingContext
from mkcv.core.models.cover_letter import CoverLetter

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


def load_letter(output: dict[str, Any] | str | None) -> CoverLetter:
    """Return the letter in ``output``.

    Raises:
        ValueError: If ``output`` is not a valid ``CoverLetter``.
    """
    if not isinstance(output, dict):
        raise ValueError("the stage produced no cover letter")
    try:
        return CoverLetter.model_validate(output)
    except ValidationError as error:
        raise ValueError(f"not a cover letter: {error.error_count()} errors") from error


def paragraphs(letter: CoverLetter) -> list[str]:
    """The opening, body, and closing paragraphs, in reading order."""
    return [
        text
        for text in (
            letter.opening_paragraph,
            *letter.body_paragraphs,
            letter.closing_paragraph,
        )
        if text.strip()
    ]


def letter_text(letter: CoverLetter) -> str:
    """The paragraphs joined by blank lines: the text a reader judges."""
    return "\n\n".join(paragraphs(letter))


def sentences(letter: CoverLetter) -> list[str]:
    """Every sentence of the paragraphs, the claims a letter makes."""
    return [
        sentence.strip()
        for paragraph in paragraphs(letter)
        for sentence in _SENTENCE_END.split(paragraph.strip())
        if sentence.strip()
    ]


def word_count(letter: CoverLetter) -> int:
    """Words in the paragraphs (salutation and sign-off excluded)."""
    return len(letter_text(letter).split())


def expected_company(ctx: GradingContext) -> str | None:
    """The company the letter must name: the case's, else the reference JD's."""
    return ctx.case.letter.company or _analysis_field(ctx, "company")


def expected_role(ctx: GradingContext) -> str | None:
    """The role the letter must name: the case's, else the reference JD's."""
    return ctx.case.letter.role or _analysis_field(ctx, "role_title")


def _analysis_field(ctx: GradingContext, name: str) -> str | None:
    analysis = ctx.reference.get("stage1_analysis")
    value = analysis.get(name) if isinstance(analysis, dict) else None
    return value if isinstance(value, str) and value.strip() else None
