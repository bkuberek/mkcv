"""Tests for recommending the best model per stage, overall and per provider."""

import statistics

import pytest

from evals.models.recommendation import OVERALL, Recommendation
from evals.models.stage_summary import StageSummary
from evals.report.recommender import DEFAULT_TIE_EPSILON, recommend
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.report_support import summary


def _overall(
    recs: list[Recommendation], stage: StageKey = StageKey.TAILOR
) -> Recommendation:
    [rec] = [r for r in recs if r.stage is stage and r.scope == OVERALL]
    return rec


def _for(recs: list[Recommendation], provider: str) -> Recommendation:
    [rec] = [r for r in recs if r.scope == provider]
    return rec


def _quality_first() -> list[StageSummary]:
    """A (0.90, $0.20), B (0.87, $0.05), C (0.95, $0.01, not eligible)."""
    return [
        summary(model="model-a", primary_score=0.90, cost=0.20),
        summary(model="model-b", primary_score=0.87, cost=0.05),
        summary(model="model-c", primary_score=0.95, cost=0.01, eligible=False),
    ]


class TestQualityFirst:
    def test_the_highest_scoring_eligible_model_wins(self) -> None:
        rec = _overall(recommend(_quality_first()))
        assert rec.model == "model-a"

    def test_a_much_cheaper_model_a_little_behind_does_not_win(self) -> None:
        rec = _overall(recommend(_quality_first()))
        assert rec.model != "model-b"

    def test_an_ineligible_model_never_wins_however_well_it_scores(self) -> None:
        rec = _overall(recommend(_quality_first()))
        assert rec.model != "model-c"

    def test_the_winner_carries_its_provider_and_score(self) -> None:
        rec = _overall(recommend(_quality_first()))
        assert (rec.provider, rec.score) == ("openai", 0.90)

    def test_the_label_joins_provider_and_model(self) -> None:
        assert _overall(recommend(_quality_first())).label == "openai/model-a"

    def test_the_reason_names_the_metric_and_the_score(self) -> None:
        rec = _overall(recommend(_quality_first()))
        assert "tailoring_judge" in rec.reason
        assert "0.90" in rec.reason

    def test_a_clear_winner_is_not_decided_by_cost(self) -> None:
        rec = _overall(recommend(_quality_first()))
        assert (rec.decided_by_cost, rec.tied_with) == (False, [])


class TestCostOnlyBreaksTies:
    def test_the_default_epsilon_is_one_hundredth(self) -> None:
        assert DEFAULT_TIE_EPSILON == 0.01

    def test_within_epsilon_the_cheaper_model_wins(self) -> None:
        rec = _overall(
            recommend(
                [
                    summary(model="dear", primary_score=0.905, cost=0.30),
                    summary(model="cheap", primary_score=0.90, cost=0.10),
                ]
            )
        )
        assert rec.model == "cheap"

    def test_a_cost_decided_tie_is_reported(self) -> None:
        rec = _overall(
            recommend(
                [
                    summary(model="dear", primary_score=0.905, cost=0.30),
                    summary(model="cheap", primary_score=0.90, cost=0.10),
                ]
            )
        )
        assert rec.decided_by_cost is True
        assert rec.tied_with == ["openai/dear"]
        assert "cheaper" in rec.reason

    def test_a_gap_just_beyond_epsilon_goes_to_the_better_model(self) -> None:
        rec = _overall(
            recommend(
                [
                    summary(model="dear", primary_score=0.911, cost=0.30),
                    summary(model="cheap", primary_score=0.90, cost=0.10),
                ]
            )
        )
        assert (rec.model, rec.decided_by_cost) == ("dear", False)

    def test_a_gap_of_exactly_epsilon_is_a_tie(self) -> None:
        rec = _overall(
            recommend(
                [
                    summary(model="dear", primary_score=0.91, cost=0.30),
                    summary(model="cheap", primary_score=0.90, cost=0.10),
                ]
            )
        )
        assert rec.model == "cheap"

    def test_the_epsilon_is_configurable(self) -> None:
        recs = recommend(
            [
                summary(model="dear", primary_score=0.95, cost=0.30),
                summary(model="cheap", primary_score=0.90, cost=0.10),
            ],
            tie_epsilon=0.05,
        )
        assert _overall(recs).model == "cheap"

    def test_a_zero_epsilon_ignores_cost_unless_scores_are_equal(self) -> None:
        recs = recommend(
            [
                summary(model="dear", primary_score=0.901, cost=0.30),
                summary(model="cheap", primary_score=0.90, cost=0.10),
            ],
            tie_epsilon=0.0,
        )
        assert _overall(recs).model == "dear"

    def test_equal_scores_and_costs_go_to_the_higher_score_then_the_faster(
        self,
    ) -> None:
        rec = _overall(
            recommend(
                [
                    summary(model="slow", primary_score=0.9, cost=0.1, p50=5.0),
                    summary(model="fast", primary_score=0.9, cost=0.1, p50=1.0),
                ]
            )
        )
        assert rec.model == "fast"

    def test_an_unknown_cost_ranks_after_a_known_one(self) -> None:
        rec = _overall(
            recommend(
                [
                    summary(model="unpriced", primary_score=0.9, cost=None),
                    summary(model="priced", primary_score=0.9, cost=5.0),
                ]
            )
        )
        assert rec.model == "priced"


class TestNoWinner:
    def test_no_eligible_model_gives_no_model(self) -> None:
        rec = _overall(recommend([summary(model="a", eligible=False)]))
        assert (rec.model, rec.provider, rec.score) == (None, None, None)

    def test_the_reason_says_no_model_is_eligible(self) -> None:
        rec = _overall(recommend([summary(model="a", eligible=False)]))
        assert rec.reason == "no eligible model"

    def test_models_without_a_quality_score_cannot_be_ranked(self) -> None:
        rec = _overall(recommend([summary(model="a", primary_score=None)]))
        assert rec.model is None
        assert "quality score" in rec.reason


class TestScopes:
    def _mixed(self) -> list[StageSummary]:
        return [
            summary(provider="openai", model="sol", primary_score=0.80, cost=0.10),
            summary(provider="google", model="argon", primary_score=0.92, cost=0.40),
            summary(provider="anthropic", model="opus", primary_score=0.88, cost=0.30),
        ]

    def test_the_overall_winner_competes_across_providers(self) -> None:
        assert _overall(recommend(self._mixed())).label == "google/argon"

    def test_each_provider_gets_its_own_winner(self) -> None:
        recs = recommend(self._mixed())
        assert {
            provider: _for(recs, provider).model
            for provider in ("anthropic", "google", "openai")
        } == {"anthropic": "opus", "google": "argon", "openai": "sol"}

    def test_each_stage_lists_overall_then_providers_alphabetically(self) -> None:
        recs = recommend(self._mixed())
        assert [r.scope for r in recs] == [OVERALL, "anthropic", "google", "openai"]

    def test_stages_follow_the_evaluation_order(self) -> None:
        recs = recommend(
            [
                summary(stage=StageKey.COVER_LETTER_GENERATE, model="a"),
                summary(stage=StageKey.REVIEW, model="a"),
                summary(stage=StageKey.ANALYZE, model="a"),
            ]
        )
        stages = [r.stage for r in recs if r.scope == OVERALL]
        assert stages == [
            StageKey.ANALYZE,
            StageKey.REVIEW,
            StageKey.COVER_LETTER_GENERATE,
        ]

    def test_a_provider_with_no_eligible_model_says_so(self) -> None:
        recs = recommend(
            [
                summary(provider="openai", model="a"),
                summary(provider="google", model="g", eligible=False),
            ]
        )
        assert _for(recs, "google").reason == "no eligible model"

    def test_no_summaries_give_no_recommendations(self) -> None:
        assert recommend([]) == []


@pytest.mark.parametrize(
    ("stage", "metric"),
    [
        (StageKey.ANALYZE, "jd_keyword_recall"),
        (StageKey.SELECT, "selection_judge"),
        (StageKey.STRUCTURE, "ats_rules"),
        (StageKey.REVIEW, "review_defect_recall"),
    ],
)
def test_the_reason_names_each_stages_primary_metric(
    stage: StageKey, metric: str
) -> None:
    rec = _overall(recommend([summary(stage=stage, model="a")]), stage)
    assert metric in rec.reason


def _noisy(model: str, *case_scores: float, cost: float = 0.1) -> StageSummary:
    """A summary whose cases score ``case_scores`` (one run each)."""
    scores = {f"case-{i}": score for i, score in enumerate(case_scores)}
    mean = sum(case_scores) / len(case_scores)
    return summary(model=model, primary_score=mean, cost=cost).model_copy(
        update={
            "case_scores": scores,
            "primary_n": len(case_scores),
            "primary_std": (
                statistics.stdev(case_scores) if len(case_scores) > 1 else None
            ),
        }
    )


class TestTooCloseToCall:
    def _close(self) -> list[StageSummary]:
        return [_noisy("a", 0.9, 0.7, 0.95), _noisy("b", 0.7, 0.9, 0.9)]

    def test_a_lead_smaller_than_its_noise_is_too_close_to_call(self) -> None:
        rec = _overall(recommend(self._close()))
        assert rec.model == "a"
        assert rec.too_close_to_call is True

    def test_the_runner_up_is_listed_with_its_lead_and_noise(self) -> None:
        [runner_up] = _overall(recommend(self._close())).runners_up
        assert runner_up.label == "openai/b"
        assert runner_up.score == pytest.approx(0.8333, abs=1e-4)
        assert runner_up.margin == pytest.approx(0.0167, abs=1e-4)
        assert runner_up.noise is not None
        assert runner_up.noise > runner_up.margin

    def test_a_steady_lead_on_every_case_is_a_clear_call(self) -> None:
        rec = _overall(
            recommend([_noisy("a", 0.9, 0.8, 0.7), _noisy("b", 0.8, 0.7, 0.6)])
        )
        assert (rec.too_close_to_call, rec.runners_up) == (False, [])

    def test_every_model_within_the_noise_is_a_runner_up(self) -> None:
        rec = _overall(
            recommend(
                [
                    *self._close(),
                    _noisy("c", 0.75, 0.95, 0.8),
                    _noisy("d", 0.1, 0.2, 0.1),
                ]
            )
        )
        assert [r.label for r in rec.runners_up] == ["openai/b", "openai/c"]

    def test_one_shared_case_falls_back_to_the_run_level_noise(self) -> None:
        a = summary(model="a", primary_score=0.80).model_copy(
            update={"case_scores": {"x": 0.80}, "primary_n": 2, "primary_std": 0.2}
        )
        b = summary(model="b", primary_score=0.75).model_copy(
            update={"case_scores": {"x": 0.75}, "primary_n": 2, "primary_std": 0.2}
        )
        rec = _overall(recommend([a, b]))
        assert rec.too_close_to_call is True
        assert rec.runners_up[0].noise == pytest.approx(0.2)

    def test_without_enough_runs_the_noise_is_unknown_and_not_flagged(self) -> None:
        a = summary(model="a", primary_score=0.80).model_copy(
            update={"case_scores": {"x": 0.80}, "primary_n": 1}
        )
        b = summary(model="b", primary_score=0.79).model_copy(
            update={"case_scores": {"x": 0.79}, "primary_n": 1}
        )
        rec = _overall(recommend([a, b], tie_epsilon=0.0))
        assert rec.too_close_to_call is False

    def test_the_reason_says_it_is_too_close_to_call(self) -> None:
        assert "too close to call" in _overall(recommend(self._close())).reason

    def test_the_winner_carries_its_standard_deviation(self) -> None:
        rec = _overall(recommend([_noisy("a", 0.9, 0.7)]))
        assert rec.std == pytest.approx(0.1414, abs=1e-4)
