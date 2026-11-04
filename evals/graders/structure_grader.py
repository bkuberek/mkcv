"""Did the structured resume keep every role the tailored content had?"""

from typing import Any

from evals.graders.grading_context import GradingContext
from evals.graders.text_normalization import (
    contains_phrase,
    normalize_company,
    normalize_text,
)
from evals.models.grade import Grade


class StructureGrader:
    """Fraction of the reference stage 3 companies that appear in the YAML.

    Company names are compared normalized (case, punctuation, and trailing
    ``Inc``/``LLC``/``Co`` ignored). None when no reference roles exist.
    """

    name = "structure"

    async def grade(self, ctx: GradingContext) -> Grade:
        """Score a stage 4 resume against the reference tailored roles."""
        companies = _reference_companies(ctx.reference)
        if not companies:
            return Grade(
                name=self.name,
                details={"reason": "no reference stage 3 roles to compare with"},
            )
        text = normalize_text(ctx.output) if isinstance(ctx.output, str) else ""
        missing = [
            name
            for name in companies
            if not contains_phrase(text, normalize_company(name))
        ]
        score = (len(companies) - len(missing)) / len(companies)
        return Grade(
            name=self.name,
            score=score,
            passed=not missing,
            details={"missing": missing},
        )


def _reference_companies(reference: dict[str, Any]) -> list[str]:
    """Return the distinct company names of the reference stage 3 roles."""
    content = reference.get("stage3_content")
    roles = content.get("roles") if isinstance(content, dict) else None
    names: list[str] = []
    for role in roles if isinstance(roles, list) else []:
        company = role.get("company") if isinstance(role, dict) else None
        if isinstance(company, str) and normalize_company(company):
            names.append(company)
    return list(dict.fromkeys(names))
