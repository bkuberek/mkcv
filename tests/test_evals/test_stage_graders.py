"""Tests for the stage-to-graders mapping (design 9.6)."""

import pytest

from evals.graders.stage_graders import (
    JUDGED_GRADES,
    PRIMARY_METRIC,
    STAGE_GRADERS,
    judge_calls,
)
from evals.stages import EVALUATED_STAGES
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.grading_support import make_case

DETERMINISTIC = {
    StageKey.ANALYZE: ["schema", "jd_keyword_recall"],
    StageKey.SELECT: ["schema", "faithfulness_extraction"],
    StageKey.TAILOR: ["schema", "faithfulness_extraction"],
    StageKey.STRUCTURE: [
        "schema",
        "ats_rules",
        "structure",
        "faithfulness_extraction",
    ],
    StageKey.REVIEW: ["schema"],
    StageKey.COVER_LETTER_GENERATE: [
        "schema",
        "cover_letter_rules",
        "faithfulness_extraction",
    ],
    StageKey.COVER_LETTER_REVIEW: ["schema"],
}


def test_every_evaluated_stage_has_graders() -> None:
    assert set(STAGE_GRADERS) == set(EVALUATED_STAGES)


@pytest.mark.parametrize("stage", EVALUATED_STAGES)
def test_each_stage_registers_its_deterministic_graders_in_order(
    stage: StageKey,
) -> None:
    names = [grader.name for grader in STAGE_GRADERS[stage]]
    assert names[: len(DETERMINISTIC[stage])] == DETERMINISTIC[stage]


def test_the_judge_graders_follow_the_deterministic_ones() -> None:
    names = {
        stage: [g.name for g in graders] for stage, graders in STAGE_GRADERS.items()
    }
    assert names == {
        StageKey.ANALYZE: ["schema", "jd_keyword_recall"],
        StageKey.SELECT: ["schema", "faithfulness_extraction", "selection_judge"],
        StageKey.TAILOR: [
            "schema",
            "faithfulness_extraction",
            "faithfulness_judge",
            "tailoring_judge",
        ],
        StageKey.STRUCTURE: [
            "schema",
            "ats_rules",
            "structure",
            "faithfulness_extraction",
        ],
        StageKey.REVIEW: ["schema", "review_defect_recall"],
        StageKey.COVER_LETTER_GENERATE: [
            "schema",
            "cover_letter_rules",
            "faithfulness_extraction",
            "faithfulness_judge",
            "cover_letter_judge",
        ],
        StageKey.COVER_LETTER_REVIEW: ["schema", "cover_letter_defect_recall"],
    }


def test_no_stage_lists_a_grader_twice() -> None:
    for graders in STAGE_GRADERS.values():
        names = [grader.name for grader in graders]
        assert len(names) == len(set(names))


def test_the_primary_metric_of_each_stage_follows_the_design() -> None:
    assert PRIMARY_METRIC == {
        StageKey.ANALYZE: "jd_keyword_recall",
        StageKey.SELECT: "selection_judge",
        StageKey.TAILOR: "tailoring_judge",
        StageKey.STRUCTURE: "ats_rules",
        StageKey.REVIEW: "review_defect_recall",
        StageKey.COVER_LETTER_GENERATE: "cover_letter_judge",
        StageKey.COVER_LETTER_REVIEW: "cover_letter_defect_recall",
    }


def test_the_judged_grades_are_the_judge_graders_names() -> None:
    assert {
        "selection_judge",
        "faithfulness_judge",
        "tailoring_judge",
        "review_defect_recall",
        "cover_letter_judge",
        "cover_letter_defect_recall",
    } == JUDGED_GRADES


@pytest.mark.parametrize(
    ("stage", "calls"),
    [
        (StageKey.ANALYZE, 0),
        (StageKey.SELECT, 1),
        (StageKey.TAILOR, 2),
        (StageKey.STRUCTURE, 0),
        (StageKey.REVIEW, 0),
        (StageKey.COVER_LETTER_GENERATE, 2),
        (StageKey.COVER_LETTER_REVIEW, 0),
    ],
)
def test_each_judge_makes_these_calls_per_run(stage: StageKey, calls: int) -> None:
    assert judge_calls(make_case(), stage) == calls


def test_probe_cases_add_their_defect_judgement() -> None:
    probe = make_case(
        review_probe_defects=["x"], cover_letter={"review_defects": ["y"]}
    )
    assert judge_calls(probe, StageKey.REVIEW) == 1
    assert judge_calls(probe, StageKey.COVER_LETTER_REVIEW) == 1
