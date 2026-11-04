"""Tests for the stage-to-graders mapping (design 9.6)."""

import pytest

from evals.graders.stage_graders import PRIMARY_METRIC, STAGE_GRADERS
from mkcv.core.models.stage_key import PIPELINE_STAGES, StageKey

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
}


def test_every_pipeline_stage_has_graders() -> None:
    assert set(STAGE_GRADERS) == set(PIPELINE_STAGES)


@pytest.mark.parametrize("stage", PIPELINE_STAGES)
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
    }
