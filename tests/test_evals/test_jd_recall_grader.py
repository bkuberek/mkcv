"""Tests for the JD keyword recall grader (REQ-EV-8)."""

from typing import Any

import pytest

from evals.graders.jd_recall_grader import JdRecallGrader
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.grading_support import (
    CASE_BY_ID,
    make_case,
    make_context,
    recorded_json,
)

grader = JdRecallGrader()


def _analysis(*terms: str) -> dict[str, Any]:
    return {"ats_keywords": list(terms), "role_summary": ""}


async def _score(keywords: list[str], output: dict[str, Any]) -> float | None:
    case = make_case(expected_keywords=keywords)
    grade = await grader.grade(make_context(StageKey.ANALYZE, output, case=case))
    return grade.score


def test_the_grader_is_named_jd_keyword_recall() -> None:
    assert grader.name == "jd_keyword_recall"


async def test_two_of_three_keywords_score_two_thirds_and_fail() -> None:
    case = make_case(expected_keywords=["Kubernetes", "Go", "Terraform"])
    output = _analysis("kubernetes", "Go")
    grade = await grader.grade(make_context(StageKey.ANALYZE, output, case=case))
    assert grade.score == pytest.approx(2 / 3)
    assert grade.passed is False


async def test_every_keyword_present_passes() -> None:
    case = make_case(expected_keywords=["Kubernetes", "Go"])
    output = _analysis("Kubernetes", "Go")
    grade = await grader.grade(make_context(StageKey.ANALYZE, output, case=case))
    assert (grade.score, grade.passed) == (1.0, True)


async def test_four_of_five_is_exactly_the_passing_threshold() -> None:
    case = make_case(expected_keywords=["a1", "b2", "c3", "d4", "e5"])
    output = _analysis("a1", "b2", "c3", "d4")
    grade = await grader.grade(make_context(StageKey.ANALYZE, output, case=case))
    assert grade.passed is True


async def test_the_missing_keywords_are_listed() -> None:
    case = make_case(expected_keywords=["Kubernetes", "Terraform"])
    grade = await grader.grade(
        make_context(StageKey.ANALYZE, _analysis("Kubernetes"), case=case)
    )
    assert grade.details["missing"] == ["Terraform"]


async def test_matching_ignores_case() -> None:
    assert await _score(["PostgreSQL"], _analysis("postgresql")) == 1.0


async def test_a_keyword_is_found_anywhere_in_the_payload() -> None:
    output = {"core_requirements": [{"skill": "incident response", "context": ""}]}
    assert await _score(["incident response"], output) == 1.0


async def test_a_short_keyword_is_not_found_inside_a_longer_word() -> None:
    output = _analysis("ongoing", "Google", "category")
    assert await _score(["Go"], output) == 0.0


async def test_a_keyword_with_symbols_is_matched_literally() -> None:
    assert await _score(["C++"], _analysis("C++", "C#")) == 1.0


async def test_the_recorded_analysis_covers_its_cases_keywords() -> None:
    case = CASE_BY_ID["backend-platform-match"]
    output = recorded_json("stage1_analysis.json")
    grade = await grader.grade(make_context(StageKey.ANALYZE, output, case=case))
    assert (grade.score, grade.passed) == (1.0, True)


async def test_a_case_without_expected_keywords_has_no_score() -> None:
    grade = await grader.grade(
        make_context(StageKey.ANALYZE, _analysis("x"), case=make_case())
    )
    assert (grade.score, grade.passed) == (None, None)


async def test_a_missing_output_scores_zero() -> None:
    case = make_case(expected_keywords=["Go"])
    grade = await grader.grade(make_context(StageKey.ANALYZE, None, case=case))
    assert grade.score == 0.0
