"""Did the review catch the defects planted in the review probe?"""

import json

from evals.graders.grading_context import GradingContext
from evals.graders.judge_call import (
    ask_judge,
    has_judge,
    judge_details,
    load_rubric,
)
from evals.graders.judged_grader import JudgedGrader
from evals.graders.text_normalization import normalize_text
from evals.models.defect_finding import DefectFinding
from evals.models.defect_judgement import DefectJudgement
from evals.models.eval_case import EvalCase
from evals.models.grade import Grade


class ReviewDefectGrader(JudgedGrader):
    """Recall of the probe's seeded defects in the review, according to a judge.

    Only the review probe case has seeded defects; for any other case, and
    without a judge, it returns None and makes no call. A finding belongs to
    the defect whose text it repeats; if the judge reworded every defect, the
    findings are taken in order.
    """

    name = "review_defect_recall"

    def applies_to(self, case: EvalCase) -> bool:
        """Only a case with seeded defects is judged."""
        return bool(case.review_probe_defects)

    async def grade(self, ctx: GradingContext) -> Grade | None:
        """Ask the judge which seeded defects ``ctx.output`` identifies."""
        defects = ctx.case.review_probe_defects
        if not defects or not has_judge(ctx):
            return None

        judgement = await ask_judge(
            ctx,
            rubric=load_rubric("review_defects"),
            user=_user_message(defects, ctx.output),
            response_model=DefectJudgement,
        )
        matched = _match(defects, judgement.findings)
        detected = sum(1 for finding in matched if finding and finding.detected)
        return Grade(
            name=self.name,
            score=detected / len(defects),
            details={
                **judge_details(ctx),
                "findings": [
                    finding.model_dump() if finding else None for finding in matched
                ],
            },
        )


def _user_message(defects: list[str], review: object) -> str:
    listed = "\n".join(f"{n}. {text}" for n, text in enumerate(defects, start=1))
    return (
        f"Planted defects:\n{listed}\n\n"
        f"Review (JSON):\n{json.dumps(review, indent=2)}\n"
    )


def _match(
    defects: list[str], findings: list[DefectFinding]
) -> list[DefectFinding | None]:
    """Return each defect's finding (None if the judge gave none)."""
    by_text = {normalize_text(finding.defect): finding for finding in findings}
    matched = [by_text.get(normalize_text(defect)) for defect in defects]
    if any(matched):
        return matched
    return [findings[i] if i < len(findings) else None for i in range(len(defects))]
