"""Helpers the grader tests share: real cases, recorded outputs, and contexts."""

import json
from pathlib import Path
from typing import Any

from evals.graders.grading_context import GradingContext
from evals.harness.case_loader import load_cases
from evals.models.criterion_score import CriterionScore
from evals.models.defect_finding import DefectFinding
from evals.models.defect_judgement import DefectJudgement
from evals.models.eval_case import EvalCase
from evals.models.faithfulness_judgement import FaithfulnessJudgement
from evals.models.faithfulness_verdict import FaithfulnessVerdict
from evals.models.rubric_judgement import RubricJudgement
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.models.experience_selection import ExperienceSelection
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.review_report import ReviewReport
from mkcv.core.models.stage_key import StageKey
from mkcv.core.models.tailored_content import TailoredContent
from mkcv.core.ports.llm import LLMPort
from tests.test_evals.conftest import RESUME_YAML, REVIEW_REPORT, recorded

FIXTURES = Path(__file__).resolve().parents[2] / "evals" / "fixtures"
RECORDED_ROOT = Path(__file__).parent / "fixtures" / "recorded"
CLEAN_DIR = RECORDED_ROOT / "backend-platform-match"
CASE_BY_ID = {case.id: case for case in load_cases(FIXTURES)}
BACKEND_KB = (FIXTURES / "personas" / "backend-engineer.md").read_text(encoding="utf-8")
CLEAN_YAML = (CLEAN_DIR / "resume.yaml").read_text(encoding="utf-8")


def recorded_json(name: str, *, folder: Path = CLEAN_DIR) -> dict[str, Any]:
    """Load a recorded stage artifact such as ``stage3_content.json``."""
    loaded: dict[str, Any] = json.loads((folder / name).read_text(encoding="utf-8"))
    return loaded


def make_case(**fields: Any) -> EvalCase:
    """Build a case that does not depend on any fixture file."""
    return EvalCase.model_validate(
        {"id": "synthetic", "persona": "p.md", "jd": "j.md", **fields}
    )


def make_context(
    stage: StageKey,
    output: dict[str, Any] | str | None,
    *,
    case: EvalCase | str = "backend-platform-match",
    kb_text: str | None = None,
    jd_text: str = "",
    reference: dict[str, Any] | None = None,
    judge: LLMPort | None = None,
    judge_model: str | None = None,
    judge_provider: str | None = None,
    evaluated_provider: str | None = None,
) -> GradingContext:
    """Build a grading context; the default case and KB are the real backend ones."""
    resolved = CASE_BY_ID[case] if isinstance(case, str) else case
    return GradingContext(
        case=resolved,
        stage=stage,
        kb_text=BACKEND_KB if kb_text is None else kb_text,
        jd_text=jd_text,
        output=output,
        reference=reference or {},
        judge=judge,
        judge_model=judge_model,
        judge_provider=judge_provider,
        evaluated_provider=evaluated_provider,
    )


def judging_stub(rubric_score: int = 4) -> StubLLMAdapter:
    """A stub that answers every pipeline stage and every judge request.

    The judge answers: every recorded tailored bullet supported, every rubric
    criterion ``rubric_score`` of 5, and every defect detected.
    """
    tailored = recorded(TailoredContent)
    assert isinstance(tailored, TailoredContent)
    bullet_count = sum(len(role.bullets) for role in tailored.roles)
    return StubLLMAdapter(
        default_response=RESUME_YAML,
        responses={
            JDAnalysis: recorded(JDAnalysis),
            ExperienceSelection: recorded(ExperienceSelection),
            TailoredContent: tailored,
            ReviewReport: REVIEW_REPORT,
            FaithfulnessJudgement: FaithfulnessJudgement(
                items=[
                    FaithfulnessVerdict(index=i, verdict="supported", evidence="KB")
                    for i in range(1, bullet_count + 1)
                ]
            ),
            RubricJudgement: RubricJudgement(
                criteria=[
                    CriterionScore(name=name, score=rubric_score, rationale="ok")
                    for name in JUDGED_CRITERIA
                ],
                summary="Good.",
            ),
            DefectJudgement: DefectJudgement(
                findings=[
                    DefectFinding(defect=text, detected=True, quote="q")
                    for text in CASE_BY_ID["review-probe"].review_probe_defects
                ]
            ),
        },
    )


JUDGED_CRITERIA = (
    "relevance",
    "keyword_integration",
    "impact",
    "clarity",
    "prioritization",
)
