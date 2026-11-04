"""Tests for recommending a model per stage and provider (REQ-EV-17, design 9.9)."""

from evals.models.stage_summary import StageSummary
from evals.report.recommender import recommend
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.report_support import summary


def _requirement_summaries() -> list[StageSummary]:
    """REQ-EV-17: A (0.90, $0.20), B (0.87, $0.05), C (0.95, $0.01, not eligible)."""
    return [
        summary(model="model-a", primary_score=0.90, cost=0.20),
        summary(model="model-b", primary_score=0.87, cost=0.05),
        summary(model="model-c", primary_score=0.95, cost=0.01, eligible=False),
    ]


class TestRequirementScenario:
    """REQ-EV-17."""

    def test_the_best_is_the_eligible_model_with_the_top_score(self) -> None:
        [rec] = recommend(_requirement_summaries())
        assert rec.best == "model-a"

    def test_the_recommended_is_the_cheapest_within_point_05_of_the_best(self) -> None:
        [rec] = recommend(_requirement_summaries())
        assert rec.recommended == "model-b"

    def test_the_economy_is_the_cheapest_scoring_at_least_point_70(self) -> None:
        [rec] = recommend(_requirement_summaries())
        assert rec.economy == "model-b"

    def test_it_names_the_stage_and_provider(self) -> None:
        [rec] = recommend(_requirement_summaries())
        assert (rec.stage, rec.provider) == (StageKey.TAILOR, "openai")

    def test_the_reason_names_the_metric_and_the_models(self) -> None:
        [rec] = recommend(_requirement_summaries())
        assert "tailoring_judge" in rec.reason
        assert "model-a" in rec.reason
        assert "model-b" in rec.reason
        assert "model-c" not in rec.reason


class TestNoEligibleModel:
    def test_all_three_choices_are_none(self) -> None:
        [rec] = recommend([summary(model="a", eligible=False)])
        assert (rec.best, rec.recommended, rec.economy) == (None, None, None)

    def test_the_reason_says_so(self) -> None:
        [rec] = recommend([summary(model="a", eligible=False)])
        assert rec.reason == "no eligible model"

    def test_models_without_a_quality_score_cannot_be_ranked(self) -> None:
        [rec] = recommend([summary(model="a", primary_score=None)])
        assert (rec.best, rec.recommended, rec.economy) == (None, None, None)
        assert "quality score" in rec.reason


class TestTieBreaks:
    def test_equal_scores_go_to_the_cheaper_model_as_best(self) -> None:
        [rec] = recommend(
            [
                summary(model="dear", primary_score=0.9, cost=0.30),
                summary(model="cheap", primary_score=0.9, cost=0.10),
            ]
        )
        assert rec.best == "cheap"

    def test_equal_scores_and_costs_go_to_the_faster_model_as_best(self) -> None:
        [rec] = recommend(
            [
                summary(model="slow", primary_score=0.9, cost=0.1, p50=5.0),
                summary(model="fast", primary_score=0.9, cost=0.1, p50=1.0),
            ]
        )
        assert rec.best == "fast"

    def test_equal_costs_recommend_the_higher_scoring_model(self) -> None:
        [rec] = recommend(
            [
                summary(model="good", primary_score=0.9, cost=0.1),
                summary(model="fine", primary_score=0.88, cost=0.1),
            ]
        )
        assert rec.recommended == "good"

    def test_an_unknown_cost_ranks_after_a_known_one(self) -> None:
        [rec] = recommend(
            [
                summary(model="unpriced", primary_score=0.9, cost=None),
                summary(model="priced", primary_score=0.9, cost=5.0),
            ]
        )
        assert (rec.best, rec.recommended) == ("priced", "priced")

    def test_an_unknown_latency_ranks_after_a_known_one(self) -> None:
        [rec] = recommend(
            [
                summary(model="unknown", primary_score=0.9, cost=0.1, p50=None),
                summary(model="known", primary_score=0.9, cost=0.1, p50=9.0),
            ]
        )
        assert rec.best == "known"


class TestThresholds:
    def test_a_model_exactly_point_05_below_the_best_is_recommendable(self) -> None:
        [rec] = recommend(
            [
                summary(model="best", primary_score=0.90, cost=0.50),
                summary(model="near", primary_score=0.85, cost=0.01),
            ]
        )
        assert rec.recommended == "near"

    def test_a_model_further_below_the_best_is_not(self) -> None:
        [rec] = recommend(
            [
                summary(model="best", primary_score=0.90, cost=0.50),
                summary(model="far", primary_score=0.84, cost=0.01),
            ]
        )
        assert rec.recommended == "best"

    def test_the_best_is_always_recommendable(self) -> None:
        [rec] = recommend([summary(model="only", primary_score=0.55, cost=1.0)])
        assert rec.recommended == "only"

    def test_the_economy_pick_needs_at_least_point_70(self) -> None:
        [rec] = recommend(
            [
                summary(model="best", primary_score=0.95, cost=0.50),
                summary(model="weak", primary_score=0.69, cost=0.01),
            ]
        )
        assert rec.economy == "best"

    def test_a_model_of_exactly_point_70_is_an_economy_candidate(self) -> None:
        [rec] = recommend(
            [
                summary(model="best", primary_score=0.95, cost=0.50),
                summary(model="ok", primary_score=0.70, cost=0.01),
            ]
        )
        assert rec.economy == "ok"

    def test_without_any_model_at_point_70_there_is_no_economy_pick(self) -> None:
        [rec] = recommend([summary(model="a", primary_score=0.60)])
        assert (rec.best, rec.economy) == ("a", None)

    def test_the_reason_says_when_no_model_reaches_the_economy_floor(self) -> None:
        [rec] = recommend([summary(model="a", primary_score=0.60)])
        assert "no eligible model scores 0.7 or more" in rec.reason

    def test_the_reason_is_silent_about_the_floor_when_one_model_reaches_it(
        self,
    ) -> None:
        [rec] = recommend([summary(model="a", primary_score=0.80)])
        assert "scores 0.7" not in rec.reason


class TestGrouping:
    def test_each_stage_and_provider_gets_a_recommendation(self) -> None:
        recs = recommend(
            [
                summary(stage=StageKey.TAILOR, provider="openai", model="a"),
                summary(stage=StageKey.TAILOR, provider="google", model="g"),
                summary(stage=StageKey.ANALYZE, provider="openai", model="a"),
            ]
        )
        assert [(r.stage.value, r.provider) for r in recs] == [
            ("analyze", "openai"),
            ("tailor", "google"),
            ("tailor", "openai"),
        ]

    def test_models_of_other_providers_do_not_compete(self) -> None:
        recs = recommend(
            [
                summary(provider="openai", model="a", primary_score=0.6, cost=0.5),
                summary(provider="google", model="g", primary_score=0.99, cost=0.01),
            ]
        )
        by_provider = {r.provider: r.best for r in recs}
        assert by_provider == {"openai": "a", "google": "g"}

    def test_no_summaries_give_no_recommendations(self) -> None:
        assert recommend([]) == []
