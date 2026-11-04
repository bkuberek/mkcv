"""Does the cover letter stick to facts found in the knowledge base?"""

import re

from evals.graders.cover_letter_text import load_letter, sentences
from evals.graders.grading_context import GradingContext
from evals.graders.text_normalization import (
    claims_term,
    contains_phrase,
    extract_numbers,
    is_supported_number,
    normalize_text,
    supported_numbers,
)
from evals.models.grade import Grade

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9+#&'-]*")
_POSSESSIVE = re.compile("['\\u2019]s$")
_HONEST_GAP = re.compile(
    r"(?i)\b(?:not|never|haven't|hasn't|have yet to|lack|new to"
    r"|eager to learn|keen to learn|excited to learn|looking forward to learning)\b"
)
_NOT_NAMES = frozenset(
    {
        "i",
        "i'm",
        "i've",
        "i'd",
        "i'll",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
    }
)


class CoverLetterFaithfulnessGrader:
    """Finds claims in a cover letter that neither the KB nor the JD supports.

    It shares its name with the resume stages' deterministic faithfulness
    grade, so the same hard gate applies. Checked, sentence by sentence:

    - every number, which the knowledge base or the job description must
      hold (``9,800`` matches ``9.8k``; a metric of the employer's is fine);
    - every capitalized word that does not start a sentence (employers,
      products, tools), which must appear in the knowledge base or the job
      description;
    - every term the letter must not claim (the case's forbidden claims and
      ``must_not_claim``), except in a sentence that states a gap ("I have
      not used ...").

    The score is ``1 - violations / checked`` and it passes with no
    violation; ``details["violations"]`` lists ``{type, text}`` with type
    ``number``, ``name``, or ``forbidden_claim``.
    """

    name = "faithfulness_extraction"

    async def grade(self, ctx: GradingContext) -> Grade:
        """Check the letter's sentences against ``ctx.kb_text`` and the JD."""
        try:
            claims = sentences(load_letter(ctx.output))
        except ValueError as error:
            return Grade(
                name=self.name,
                score=0.0,
                passed=False,
                details={"violations": [], "checked": 0, "error": str(error)},
            )

        sources = f"{ctx.kb_text}\n{ctx.jd_text}"
        violations: list[dict[str, str]] = []
        checked = _check_numbers(claims, sources, violations)
        checked += _check_names(claims, normalize_text(sources), violations)
        checked += _check_forbidden(claims, ctx.case.cover_letter_forbidden, violations)
        return Grade(
            name=self.name,
            score=1.0 - len(violations) / max(1, checked),
            passed=not violations,
            details={"violations": violations, "checked": checked},
        )


def _check_numbers(
    claims: list[str], sources: str, violations: list[dict[str, str]]
) -> int:
    supported = supported_numbers(sources)
    checked = 0
    for sentence in claims:
        for token in extract_numbers(sentence):
            checked += 1
            if not is_supported_number(token, supported):
                violations.append({"type": "number", "text": token})
    return checked


def _check_names(
    claims: list[str], knowledge: str, violations: list[dict[str, str]]
) -> int:
    checked = 0
    for sentence in claims:
        for word in _WORD.findall(sentence)[1:]:
            name = _POSSESSIVE.sub("", word).strip("'-")
            if not name[:1].isupper() or name.lower() in _NOT_NAMES:
                continue
            checked += 1
            if not contains_phrase(knowledge, normalize_text(name)):
                violations.append({"type": "name", "text": name})
    return checked


def _check_forbidden(
    claims: list[str], terms: list[str], violations: list[dict[str, str]]
) -> int:
    for term in terms:
        if any(
            claims_term(sentence, term) and not _HONEST_GAP.search(sentence)
            for sentence in claims
        ):
            violations.append({"type": "forbidden_claim", "text": term})
    return len(terms)
