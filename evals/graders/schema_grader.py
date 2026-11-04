"""Does the output have the shape its stage promises?"""

from pydantic import BaseModel, ValidationError

from evals.graders.grading_context import GradingContext
from evals.graders.resume_yaml import load_cv, structure_problems
from evals.models.grade import Grade
from mkcv.core.models.cover_letter import CoverLetter
from mkcv.core.models.cover_letter_review import CoverLetterReview
from mkcv.core.models.experience_selection import ExperienceSelection
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.review_report import ReviewReport
from mkcv.core.models.stage_key import StageKey
from mkcv.core.models.tailored_content import TailoredContent

MAX_REPORTED_ERRORS = 5

STAGE_MODELS: dict[StageKey, type[BaseModel]] = {
    StageKey.ANALYZE: JDAnalysis,
    StageKey.SELECT: ExperienceSelection,
    StageKey.TAILOR: TailoredContent,
    StageKey.REVIEW: ReviewReport,
    StageKey.COVER_LETTER_GENERATE: CoverLetter,
    StageKey.COVER_LETTER_REVIEW: CoverLetterReview,
}


class SchemaGrader:
    """Scores 1.0 when the output validates against its stage's model.

    Stages 1-3 and 5 validate the artifact against ``JDAnalysis``,
    ``ExperienceSelection``, ``TailoredContent``, or ``ReviewReport``, and the
    cover letter stages against ``CoverLetter`` or ``CoverLetterReview``.
    Stage 4 needs YAML with a ``cv.name`` string and a non-empty
    ``cv.sections``.
    """

    name = "schema"

    async def grade(self, ctx: GradingContext) -> Grade:
        """Return 1.0 with no errors, or 0.0 listing the first few errors."""
        errors = self._errors(ctx)
        return Grade(
            name=self.name,
            score=0.0 if errors else 1.0,
            passed=not errors,
            details={"errors": errors[:MAX_REPORTED_ERRORS]},
        )

    def _errors(self, ctx: GradingContext) -> list[str]:
        if ctx.output is None:
            return ["the stage produced no output"]
        if ctx.stage is StageKey.STRUCTURE:
            return _resume_errors(ctx.output)
        if not isinstance(ctx.output, dict):
            return ["expected a JSON object"]
        try:
            STAGE_MODELS[ctx.stage].model_validate(ctx.output)
        except ValidationError as error:
            return [
                f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
                for item in error.errors()
            ]
        return []


def _resume_errors(output: dict[str, object] | str) -> list[str]:
    if not isinstance(output, str):
        return ["expected YAML text"]
    try:
        cv = load_cv(output)
    except ValueError as error:
        return [str(error)]
    return structure_problems(cv)
