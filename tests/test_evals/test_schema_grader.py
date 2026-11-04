"""Tests for the schema grader (REQ-EV-7)."""

from typing import Any

import pytest

from evals.graders.schema_grader import SchemaGrader
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.conftest import REVIEW_REPORT
from tests.test_evals.grading_support import (
    CLEAN_YAML,
    make_context,
    recorded_json,
)

grader = SchemaGrader()

VALID_ARTIFACTS = [
    (StageKey.ANALYZE, "stage1_analysis.json"),
    (StageKey.SELECT, "stage2_selection.json"),
    (StageKey.TAILOR, "stage3_content.json"),
]


def test_the_grader_is_named_schema() -> None:
    assert grader.name == "schema"


class TestJsonStages:
    @pytest.mark.parametrize(("stage", "name"), VALID_ARTIFACTS)
    async def test_a_valid_artifact_scores_one(
        self, stage: StageKey, name: str
    ) -> None:
        grade = await grader.grade(make_context(stage, recorded_json(name)))
        assert (grade.score, grade.passed) == (1.0, True)

    async def test_a_valid_review_report_scores_one(self) -> None:
        output = REVIEW_REPORT.model_dump()
        grade = await grader.grade(make_context(StageKey.REVIEW, output))
        assert (grade.score, grade.passed) == (1.0, True)

    async def test_a_missing_required_field_scores_zero(self) -> None:
        output = recorded_json("stage1_analysis.json")
        del output["company"]
        grade = await grader.grade(make_context(StageKey.ANALYZE, output))
        assert (grade.score, grade.passed) == (0.0, False)

    async def test_the_failure_names_the_offending_field(self) -> None:
        output = recorded_json("stage1_analysis.json")
        del output["company"]
        grade = await grader.grade(make_context(StageKey.ANALYZE, output))
        assert "company" in str(grade.details["errors"])

    async def test_a_wrong_type_scores_zero(self) -> None:
        output = recorded_json("stage2_selection.json")
        output["skills_to_highlight"] = "Kubernetes"
        grade = await grader.grade(make_context(StageKey.SELECT, output))
        assert grade.score == 0.0

    async def test_the_artifact_is_checked_against_its_own_stage_model(self) -> None:
        output = recorded_json("stage1_analysis.json")
        grade = await grader.grade(make_context(StageKey.TAILOR, output))
        assert grade.score == 0.0

    async def test_a_review_out_of_range_score_scores_zero(self) -> None:
        output = REVIEW_REPORT.model_dump() | {"overall_score": 140}
        grade = await grader.grade(make_context(StageKey.REVIEW, output))
        assert grade.score == 0.0

    async def test_only_a_handful_of_errors_are_reported(self) -> None:
        grade = await grader.grade(make_context(StageKey.ANALYZE, {}))
        assert 1 <= len(grade.details["errors"]) <= 5

    async def test_a_missing_output_scores_zero(self) -> None:
        grade = await grader.grade(make_context(StageKey.ANALYZE, None))
        assert (grade.score, grade.passed) == (0.0, False)

    async def test_text_where_a_json_object_belongs_is_named_as_such(self) -> None:
        grade = await grader.grade(make_context(StageKey.ANALYZE, "company: Acme"))
        assert grade.details["errors"] == ["expected a JSON object"]


class TestStructureStage:
    async def test_the_recorded_resume_scores_one(self) -> None:
        grade = await grader.grade(make_context(StageKey.STRUCTURE, CLEAN_YAML))
        assert (grade.score, grade.passed) == (1.0, True)

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "cv: [unclosed",
            "- just\n- a list\n",
            "cv: just text\n",
            "cv:\n  name: Alex\n",
            "cv:\n  name: Alex\n  sections: {}\n",
            "cv:\n  name: Alex\n  sections: [a, b]\n",
            "cv:\n  sections:\n    skills: []\n",
            "cv:\n  name: 42\n  sections:\n    skills: []\n",
            "cv:\n  name: ' '\n  sections:\n    skills: []\n",
        ],
        ids=[
            "empty",
            "unparseable",
            "not-a-mapping",
            "cv-is-text",
            "no-sections",
            "empty-sections",
            "sections-is-a-list",
            "no-name",
            "name-is-a-number",
            "name-is-blank",
        ],
    )
    async def test_yaml_without_a_named_cv_and_sections_scores_zero(
        self, text: str
    ) -> None:
        grade = await grader.grade(make_context(StageKey.STRUCTURE, text))
        assert (grade.score, grade.passed) == (0.0, False)

    async def test_a_failure_says_why(self) -> None:
        grade = await grader.grade(make_context(StageKey.STRUCTURE, "cv:\n  name: A\n"))
        assert "cv.sections" in grade.details["errors"][0]

    async def test_a_non_text_output_scores_zero(self) -> None:
        output: dict[str, Any] = {"cv": {}}
        grade = await grader.grade(make_context(StageKey.STRUCTURE, output))
        assert grade.score == 0.0
