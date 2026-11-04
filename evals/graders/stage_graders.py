"""Which graders score each stage, and which grade is its quality metric."""

from evals.graders.ats_rules_grader import AtsRulesGrader
from evals.graders.faithfulness_extraction_grader import FaithfulnessExtractionGrader
from evals.graders.grader import Grader
from evals.graders.jd_recall_grader import JdRecallGrader
from evals.graders.schema_grader import SchemaGrader
from evals.graders.structure_grader import StructureGrader
from mkcv.core.models.stage_key import StageKey

STAGE_GRADERS: dict[StageKey, tuple[Grader, ...]] = {
    StageKey.ANALYZE: (SchemaGrader(), JdRecallGrader()),
    StageKey.SELECT: (SchemaGrader(), FaithfulnessExtractionGrader()),
    StageKey.TAILOR: (SchemaGrader(), FaithfulnessExtractionGrader()),
    StageKey.STRUCTURE: (
        SchemaGrader(),
        AtsRulesGrader(),
        StructureGrader(),
        FaithfulnessExtractionGrader(),
    ),
    StageKey.REVIEW: (SchemaGrader(),),
}
"""Graders run on each stage's ``ok`` output, in order (design 9.6).

The LLM-judge graders are added to the same tuples where the judge is wired in.
"""

PRIMARY_METRIC: dict[StageKey, str] = {
    StageKey.ANALYZE: "jd_keyword_recall",
    StageKey.SELECT: "selection_judge",
    StageKey.TAILOR: "tailoring_judge",
    StageKey.STRUCTURE: "ats_rules",
    StageKey.REVIEW: "review_defect_recall",
}
"""The grade that ranks models at each stage (design 9.6)."""
