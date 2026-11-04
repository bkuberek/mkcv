"""Does the output stick to facts found in the knowledge base?"""

from evals.graders.extracted_claims import ExtractedClaims, extract_claims
from evals.graders.grading_context import GradingContext
from evals.graders.text_normalization import (
    claims_term,
    contains_phrase,
    extract_numbers,
    is_supported_number,
    normalize_company,
    normalize_text,
    supported_numbers,
)
from evals.models.grade import Grade


class FaithfulnessExtractionGrader:
    """Finds claims in the output that the knowledge base does not support.

    Checked claims are the numbers in bullets, the companies and titles of the
    roles, and each of the case's forbidden terms. The score is
    ``1 - violations / checked`` and the grade passes with no violation.
    ``details["violations"]`` lists each as ``{type, text}`` where type is
    ``number``, ``company``, ``title``, or ``forbidden_claim``.

    A number is supported when the knowledge base holds it, with or without
    its unit (``40%`` supports ``40 percent`` and ``40``).
    """

    name = "faithfulness_extraction"

    async def grade(self, ctx: GradingContext) -> Grade:
        """Check the output's claims against ``ctx.kb_text``."""
        claims = extract_claims(ctx.stage, ctx.output)
        if claims is None:
            return Grade(
                name=self.name,
                score=0.0,
                passed=False,
                details={
                    "violations": [],
                    "checked": 0,
                    "error": "no claims could be read from the output",
                },
            )

        violations: list[dict[str, str]] = []
        checked = _check_numbers(claims, ctx.kb_text, violations)
        checked += _check_names(claims, ctx.kb_text, violations)
        checked += _check_forbidden(claims, ctx.case.forbidden_claims, violations)
        score = 1.0 - len(violations) / max(1, checked)
        return Grade(
            name=self.name,
            score=score,
            passed=not violations,
            details={"violations": violations, "checked": checked},
        )


def _check_numbers(
    claims: ExtractedClaims, kb_text: str, violations: list[dict[str, str]]
) -> int:
    supported = supported_numbers(kb_text)
    checked = 0
    for bullet in claims.bullets:
        for token in extract_numbers(bullet):
            checked += 1
            if not is_supported_number(token, supported):
                violations.append({"type": "number", "text": token})
    return checked


def _check_names(
    claims: ExtractedClaims, kb_text: str, violations: list[dict[str, str]]
) -> int:
    knowledge = normalize_text(kb_text)
    checked = 0
    for kind, names in (("company", claims.employers), ("title", claims.titles)):
        for name in names:
            normalized = normalize_company(name)
            if not normalized:
                continue
            checked += 1
            if not contains_phrase(knowledge, normalized):
                violations.append({"type": kind, "text": name})
    return checked


def _check_forbidden(
    claims: ExtractedClaims, terms: list[str], violations: list[dict[str, str]]
) -> int:
    texts = [*claims.bullets, *claims.skills]
    for term in terms:
        if any(claims_term(text, term) for text in texts):
            violations.append({"type": "forbidden_claim", "text": term})
    return len(terms)
