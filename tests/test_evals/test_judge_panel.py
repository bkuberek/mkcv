"""Tests for combining every panel judge's grade into one grade."""

import pytest

from evals.graders.judge_panel import AGREEMENT_SPREAD, PanelVerdict, combine_panel
from evals.models.grade import Grade

OPUS = ("anthropic/claude-opus-5-5", "anthropic")
ASTRA = ("openai/gpt-6-astra", "openai")
ARGON = ("google/gemini-4-argon", "google")


def _verdict(
    judge: tuple[str, str],
    score: float | None,
    *,
    passed: bool | None = None,
    **details: object,
) -> PanelVerdict:
    label, provider = judge
    return PanelVerdict(
        judge=label,
        provider=provider,
        grade=Grade(
            name="tailoring_judge", score=score, passed=passed, details=details
        ),
    )


def _combine(*verdicts: PanelVerdict, evaluated: str = "openai") -> Grade:
    grade = combine_panel("tailoring_judge", verdicts, evaluated_provider=evaluated)
    assert grade is not None
    return grade


class TestScore:
    def test_the_score_is_the_mean_of_every_judge(self) -> None:
        grade = _combine(
            _verdict(OPUS, 0.8), _verdict(ASTRA, 0.6), _verdict(ARGON, 0.7)
        )
        assert grade.score == pytest.approx(0.7)

    def test_the_grade_keeps_its_name(self) -> None:
        assert _combine(_verdict(OPUS, 0.8)).name == "tailoring_judge"

    def test_each_judges_score_is_kept(self) -> None:
        grade = _combine(_verdict(OPUS, 0.8, summary="fine"), _verdict(ARGON, 0.6))
        assert [(s.judge, s.score) for s in grade.judge_scores] == [
            ("anthropic/claude-opus-5-5", 0.8),
            ("google/gemini-4-argon", 0.6),
        ]
        assert grade.judge_scores[0].details == {"summary": "fine"}

    def test_a_judge_that_failed_is_left_out_of_the_mean(self) -> None:
        grade = _combine(_verdict(OPUS, 0.8), _verdict(ARGON, None, error="down"))
        assert grade.score == 0.8
        assert grade.judge_scores[1].details["error"] == "down"

    def test_when_every_judge_failed_there_is_no_score_and_the_errors_show(
        self,
    ) -> None:
        grade = _combine(_verdict(OPUS, None, error="boom"), _verdict(ARGON, None))
        assert grade.score is None
        assert "anthropic/claude-opus-5-5: boom" in grade.details["error"]

    def test_judges_that_did_not_apply_give_no_grade(self) -> None:
        verdict = PanelVerdict(judge=OPUS[0], provider=OPUS[1], grade=None)
        assert combine_panel("x", [verdict], evaluated_provider="openai") is None

    def test_an_empty_panel_gives_no_grade(self) -> None:
        assert combine_panel("x", [], evaluated_provider="openai") is None

    def test_the_details_list_the_judges_that_scored(self) -> None:
        grade = _combine(_verdict(OPUS, 0.8), _verdict(ARGON, None, error="down"))
        assert grade.details["judges"] == ["anthropic/claude-opus-5-5"]


class TestSelfPreference:
    def test_the_independent_score_leaves_out_the_models_own_provider(self) -> None:
        grade = _combine(
            _verdict(OPUS, 0.6), _verdict(ASTRA, 1.0), _verdict(ARGON, 0.8)
        )
        assert grade.independent_score == pytest.approx(0.7)

    def test_the_own_providers_judge_is_marked(self) -> None:
        grade = _combine(_verdict(OPUS, 0.6), _verdict(ASTRA, 1.0))
        assert [s.self_judged for s in grade.judge_scores] == [False, True]

    def test_a_grade_with_another_providers_judge_is_not_self_judged(self) -> None:
        grade = _combine(_verdict(OPUS, 0.6), _verdict(ASTRA, 1.0))
        assert grade.details["self_judged"] is False

    def test_a_grade_scored_only_by_its_own_provider_is_self_judged(self) -> None:
        grade = _combine(_verdict(ASTRA, 1.0), _verdict(OPUS, None, error="down"))
        assert grade.details["self_judged"] is True
        assert grade.independent_score is None

    def test_without_a_judge_from_the_same_provider_both_scores_agree(self) -> None:
        grade = _combine(_verdict(OPUS, 0.6), _verdict(ARGON, 0.8), evaluated="stub")
        assert grade.independent_score == grade.score


class TestPassed:
    def test_it_fails_when_one_of_two_independent_judges_fails_it(self) -> None:
        grade = _combine(
            _verdict(OPUS, 0.9, passed=False), _verdict(ARGON, 1.0, passed=True)
        )
        assert grade.passed is False

    def test_it_passes_when_one_of_three_independent_judges_fails_it(self) -> None:
        grade = _combine(
            _verdict(OPUS, 0.9, passed=False),
            _verdict(ARGON, 1.0, passed=True),
            _verdict(("x/y", "x"), 1.0, passed=True),
        )
        assert grade.passed is True

    def test_the_own_providers_judge_cannot_pass_it(self) -> None:
        grade = _combine(
            _verdict(OPUS, 0.9, passed=False), _verdict(ASTRA, 1.0, passed=True)
        )
        assert grade.passed is False

    def test_the_own_providers_judge_decides_when_it_is_the_only_one(self) -> None:
        grade = _combine(_verdict(ASTRA, 0.9, passed=False))
        assert grade.passed is False

    def test_grades_without_a_pass_flag_stay_without_one(self) -> None:
        assert _combine(_verdict(OPUS, 0.8), _verdict(ARGON, 0.6)).passed is None


class TestSpread:
    def test_the_spread_is_the_gap_between_the_highest_and_lowest_score(
        self,
    ) -> None:
        grade = _combine(
            _verdict(OPUS, 0.8), _verdict(ASTRA, 0.6), _verdict(ARGON, 0.7)
        )
        assert grade.details["spread"] == pytest.approx(0.2)

    def test_one_judge_has_no_spread(self) -> None:
        assert _combine(_verdict(OPUS, 0.8)).details["spread"] is None

    def test_judges_agree_when_they_are_a_tenth_apart_or_less(self) -> None:
        assert AGREEMENT_SPREAD == 0.1
