"""Did a review catch the defects planted in the output it reviewed?"""

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


class DefectRecallGrader(JudgedGrader):
    """Base for the recall of seeded defects in a review, according to a judge.

    Only a probe case has seeded defects; for any other case, and without a
    judge, it returns None and makes no call. A finding belongs to the defect
    whose text it repeats; if the judge reworded every defect, the findings
    are taken in order. Subclasses set ``name`` and ``rubric`` and say where
    the case keeps its defects.
    """

    name: str
    rubric: str

    def defects(self, case: EvalCase) -> list[str]:
        """The defects seeded for ``case``."""
        raise NotImplementedError

    def applies_to(self, case: EvalCase) -> bool:
        """Only a case with seeded defects is judged."""
        return bool(self.defects(case))

    async def grade(self, ctx: GradingContext) -> Grade | None:
        """Ask the judge which seeded defects ``ctx.output`` identifies."""
        defects = self.defects(ctx.case)
        if not defects or not has_judge(ctx):
            return None

        judgement = await ask_judge(
            ctx,
            rubric=load_rubric(self.rubric),
            prefix=_planted(defects),
            user=f"Review (JSON):\n{json.dumps(ctx.output, indent=2)}\n",
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


def _planted(defects: list[str]) -> str:
    listed = "\n".join(f"{n}. {text}" for n, text in enumerate(defects, start=1))
    return f"Planted defects:\n{listed}\n"


def _match(
    defects: list[str], findings: list[DefectFinding]
) -> list[DefectFinding | None]:
    """Return each defect's finding (None if the judge gave none)."""
    by_text = {normalize_text(finding.defect): finding for finding in findings}
    matched = [by_text.get(normalize_text(defect)) for defect in defects]
    if any(matched):
        return matched
    return [findings[i] if i < len(findings) else None for i in range(len(defects))]
