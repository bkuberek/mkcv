"""Which graders score each stage, and which grade is its quality metric."""

from evals.graders.ats_rules_grader import AtsRulesGrader
from evals.graders.cover_letter_defect_grader import CoverLetterDefectGrader
from evals.graders.cover_letter_faithfulness_grader import (
    CoverLetterFaithfulnessGrader,
)
from evals.graders.cover_letter_faithfulness_judge_grader import (
    CoverLetterFaithfulnessJudgeGrader,
)
from evals.graders.cover_letter_judge_grader import CoverLetterJudgeGrader
from evals.graders.cover_letter_rules_grader import CoverLetterRulesGrader
from evals.graders.faithfulness_extraction_grader import FaithfulnessExtractionGrader
from evals.graders.faithfulness_judge_grader import FaithfulnessJudgeGrader
from evals.graders.grader import Grader
from evals.graders.jd_recall_grader import JdRecallGrader
from evals.graders.judged_grader import JudgedGrader
from evals.graders.review_defect_grader import ReviewDefectGrader
from evals.graders.schema_grader import SchemaGrader
from evals.graders.selection_judge_grader import SelectionJudgeGrader
from evals.graders.structure_grader import StructureGrader
from evals.graders.tailoring_judge_grader import TailoringJudgeGrader
from evals.models.eval_case import EvalCase
from mkcv.core.models.stage_key import StageKey

STAGE_GRADERS: dict[StageKey, tuple[Grader, ...]] = {
    StageKey.ANALYZE: (SchemaGrader(), JdRecallGrader()),
    StageKey.SELECT: (
        SchemaGrader(),
        FaithfulnessExtractionGrader(),
        SelectionJudgeGrader(),
    ),
    StageKey.TAILOR: (
        SchemaGrader(),
        FaithfulnessExtractionGrader(),
        FaithfulnessJudgeGrader(),
        TailoringJudgeGrader(),
    ),
    StageKey.STRUCTURE: (
        SchemaGrader(),
        AtsRulesGrader(),
        StructureGrader(),
        FaithfulnessExtractionGrader(),
    ),
    StageKey.REVIEW: (SchemaGrader(), ReviewDefectGrader()),
    StageKey.COVER_LETTER_GENERATE: (
        SchemaGrader(),
        CoverLetterRulesGrader(),
        CoverLetterFaithfulnessGrader(),
        CoverLetterFaithfulnessJudgeGrader(),
        CoverLetterJudgeGrader(),
    ),
    StageKey.COVER_LETTER_REVIEW: (SchemaGrader(), CoverLetterDefectGrader()),
}
"""Graders run on each stage's ``ok`` output, in order (design 9.6).

A judge grader steps aside (returns None) when the run has no judge, and the
review defect grader does so on every case but the probe.
"""

JUDGE_STAGES: frozenset[StageKey] = frozenset(
    stage
    for stage, graders in STAGE_GRADERS.items()
    if any(isinstance(grader, JudgedGrader) for grader in graders)
)
"""Stages with a judge grader (the review one applies to the probe case only)."""

JUDGED_GRADES: frozenset[str] = frozenset(
    grader.name
    for graders in STAGE_GRADERS.values()
    for grader in graders
    if isinstance(grader, JudgedGrader)
)
"""Names of the grades the judge panel scores."""


def judge_calls(case: EvalCase, stage: StageKey) -> int:
    """Return the calls each judge makes to grade one run of ``case`` at ``stage``."""
    return sum(
        1
        for grader in STAGE_GRADERS.get(stage, ())
        if isinstance(grader, JudgedGrader) and grader.applies_to(case)
    )


PRIMARY_METRIC: dict[StageKey, str] = {
    StageKey.ANALYZE: "jd_keyword_recall",
    StageKey.SELECT: "selection_judge",
    StageKey.TAILOR: "tailoring_judge",
    StageKey.STRUCTURE: "ats_rules",
    StageKey.REVIEW: "review_defect_recall",
    StageKey.COVER_LETTER_GENERATE: "cover_letter_judge",
    StageKey.COVER_LETTER_REVIEW: "cover_letter_defect_recall",
}
"""The grade that ranks models at each stage (design 9.6)."""
