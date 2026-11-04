"""Check every reference artifact against its case's knowledge base, by rule."""

import json
from collections.abc import Sequence
from typing import Any

from evals.graders.cover_letter_faithfulness_grader import (
    CoverLetterFaithfulnessGrader,
)
from evals.graders.faithfulness_extraction_grader import FaithfulnessExtractionGrader
from evals.graders.grader import Grader
from evals.graders.grading_context import GradingContext
from evals.harness.stage_runner import RESUME_FILE
from evals.models.eval_case import COVER_LETTER_FILE, REFERENCE_FILES, EvalCase
from evals.models.reference_finding import ReferenceFinding
from mkcv.core.models.stage_key import StageKey

_CHECKED: tuple[tuple[StageKey, str, Grader], ...] = (
    (
        StageKey.SELECT,
        REFERENCE_FILES[StageKey.SELECT][0],
        FaithfulnessExtractionGrader(),
    ),
    (
        StageKey.TAILOR,
        REFERENCE_FILES[StageKey.TAILOR][0],
        FaithfulnessExtractionGrader(),
    ),
    (StageKey.STRUCTURE, RESUME_FILE, FaithfulnessExtractionGrader()),
    (
        StageKey.COVER_LETTER_GENERATE,
        COVER_LETTER_FILE,
        CoverLetterFaithfulnessGrader(),
    ),
)
"""The reference files that make claims, the stage they stand for, and the grader."""


async def check_references(cases: Sequence[EvalCase]) -> list[ReferenceFinding]:
    """Run the deterministic faithfulness graders over each case's references.

    Every number, employer, title, forbidden term (and, in a cover letter,
    every name) the knowledge base does not support is listed, so references
    can be reviewed before they are committed. Files a case does not have
    are skipped.
    """
    findings: list[ReferenceFinding] = []
    for case in cases:
        for stage, name, grader in _CHECKED:
            path = case.reference_dir / name
            if path.is_file():
                findings.append(
                    await _check(case, stage, name, grader, path.read_text())
                )
    return findings


async def _check(
    case: EvalCase, stage: StageKey, name: str, grader: Grader, text: str
) -> ReferenceFinding:
    probe = bool(case.review_probe_defects) or case.is_cover_letter_probe
    try:
        output: dict[str, Any] | str = text if name == RESUME_FILE else json.loads(text)
    except json.JSONDecodeError as error:
        return ReferenceFinding(
            case_id=case.id, artifact=name, error=str(error), probe=probe
        )
    context = GradingContext(
        case=case,
        stage=stage,
        kb_text=case.kb_text,
        jd_text=case.jd_text,
        output=output,
    )
    grade = await grader.grade(context)
    details = grade.details if grade is not None else {}
    return ReferenceFinding(
        case_id=case.id,
        artifact=name,
        violations=list(details.get("violations", [])),
        error=details.get("error"),
        probe=probe,
    )
