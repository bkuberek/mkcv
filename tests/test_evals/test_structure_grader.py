"""Tests for the structure grader (REQ-EV-11)."""

from typing import Any

import pytest

from evals.graders.structure_grader import StructureGrader
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.grading_support import (
    CLEAN_YAML,
    make_context,
    recorded_json,
)

grader = StructureGrader()


def _reference(*companies: str) -> dict[str, Any]:
    return {"stage3_content": {"roles": [{"company": name} for name in companies]}}


def _yaml(*companies: str) -> str:
    entries = "".join(
        f"      - company: {name}\n        position: Engineer\n" for name in companies
    )
    return f"cv:\n  name: Alex\n  sections:\n    experience:\n{entries}"


async def _grade(yaml_text: str, reference: dict[str, Any] | None) -> Any:
    return await grader.grade(
        make_context(StageKey.STRUCTURE, yaml_text, reference=reference)
    )


def test_the_grader_is_named_structure() -> None:
    assert grader.name == "structure"


async def test_one_of_two_reference_companies_scores_one_half() -> None:
    grade = await _grade(_yaml("Initech"), _reference("Initech", "Globex"))
    assert grade.score == 0.5
    assert grade.passed is False


async def test_every_reference_company_present_scores_one() -> None:
    grade = await _grade(_yaml("Initech", "Globex"), _reference("Initech", "Globex"))
    assert (grade.score, grade.passed) == (1.0, True)


async def test_a_company_with_two_roles_counts_once() -> None:
    grade = await _grade(_yaml("Initech"), _reference("Initech", "Initech", "Globex"))
    assert grade.score == 0.5


async def test_the_missing_companies_are_listed() -> None:
    grade = await _grade(_yaml("Initech"), _reference("Initech", "Globex"))
    assert grade.details["missing"] == ["Globex"]


async def test_the_recorded_resume_keeps_the_recorded_roles() -> None:
    reference = {"stage3_content": recorded_json("stage3_content.json")}
    grade = await _grade(CLEAN_YAML, reference)
    assert grade.score == 1.0


async def test_company_suffixes_and_punctuation_do_not_matter() -> None:
    grade = await _grade(_yaml("Initech"), _reference("Initech, Inc."))
    assert grade.score == 1.0


async def test_case_does_not_matter() -> None:
    grade = await _grade(_yaml("INITECH"), _reference("Initech"))
    assert grade.score == 1.0


async def test_a_company_may_appear_anywhere_in_the_text() -> None:
    text = "cv:\n  name: Alex\n  sections:\n    summary:\n      - Ex-Globex engineer\n"
    grade = await _grade(text, _reference("Globex"))
    assert grade.score == 1.0


@pytest.mark.parametrize("reference", [None, {}, {"stage3_content": {"roles": []}}])
async def test_without_reference_roles_there_is_nothing_to_score(
    reference: dict[str, Any] | None,
) -> None:
    grade = await _grade(_yaml("Initech"), reference)
    assert (grade.score, grade.passed) == (None, None)


async def test_a_missing_output_scores_zero() -> None:
    grade = await grader.grade(
        make_context(StageKey.STRUCTURE, None, reference=_reference("Initech"))
    )
    assert grade.score == 0.0
