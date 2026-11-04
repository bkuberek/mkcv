"""Tests for the matrix cost estimate (REQ-EV-21, design 9.8)."""

import pytest

from evals.harness.cost_estimator import (
    JUDGE_INPUT_TOKENS,
    JUDGE_OUTPUT_TOKENS,
    assumed_survivors,
    estimate_matrix_cost,
    estimate_tournament_cost,
)
from evals.models.caching_settings import CachingSettings
from evals.models.cost_estimate import CostEstimate
from evals.models.eval_case import EvalCase
from evals.models.judge_config import JudgeConfig
from evals.models.matrix_config import MatrixConfig
from evals.models.matrix_model import MatrixModel
from evals.models.run_settings import RunSettings
from evals.models.tournament_settings import TournamentSettings
from mkcv.core.catalog.stage_requirements import STAGE_REQUIREMENTS
from mkcv.core.models.model_capability import ModelCapability
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.stage_key import StageKey

HAIKU = "anthropic/claude-haiku-5-5"
JUDGE = JudgeConfig(provider="anthropic", model="claude-opus-5-5")
PER_MILLION = 1e6


def _case(case_id: str = "alpha", **fields: object) -> EvalCase:
    return EvalCase(id=case_id, persona="persona.md", jd="jd.md", **fields)  # type: ignore[arg-type]


def _matrix(
    stages: list[StageKey],
    *,
    models: list[MatrixModel] | None = None,
    repeats: int = 1,
) -> MatrixConfig:
    return MatrixConfig(
        run=RunSettings(stages=stages, repeats=repeats),
        judge=JUDGE,
        reference=JUDGE,
        models=models or [MatrixModel(provider="anthropic", model="claude-haiku-5-5")],
    )


def _priced(
    provider: str, model: str, cost_in: float, cost_out: float
) -> ModelCapability:
    return ModelCapability(
        provider=provider,
        match=model,
        input_price_per_mtok=cost_in,
        output_price_per_mtok=cost_out,
    )


def _unit_model(name: str) -> MatrixModel:
    return MatrixModel(provider="p", model=name)


JUDGED_CATALOG = ModelCatalog(
    [_priced("p", "m", 0.0, 0.0), _priced("anthropic", "claude-opus-5-5", 5.0, 25.0)]
)


def test_a_judge_call_is_estimated_at_the_documented_size() -> None:
    assert (JUDGE_INPUT_TOKENS, JUDGE_OUTPUT_TOKENS) == (6000, 1500)


class TestEvaluatedModelCost:
    def test_two_cases_on_analyze_cost_the_documented_amount(self) -> None:
        """REQ-EV-21: 2 x (4000 x 0.10 + 2000 x 0.50) / 1e6 = $0.0028."""
        estimate = estimate_matrix_cost(
            _matrix([StageKey.ANALYZE]),
            [_case("one"), _case("two")],
            ModelCatalog.builtin(),
        )
        assert estimate.model_costs[HAIKU] == pytest.approx(0.0028)

    def test_analyze_has_no_judge_cost(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix([StageKey.ANALYZE]), [_case()], ModelCatalog.builtin()
        )
        assert (estimate.judge_calls, estimate.judge_cost_usd) == (0, 0.0)
        assert estimate.judges == []

    def test_total_is_the_evaluated_cost_when_there_are_no_judge_calls(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix([StageKey.ANALYZE]), [_case()], ModelCatalog.builtin()
        )
        assert estimate.total_usd == pytest.approx(0.0014)

    def test_repeats_multiply_the_cost(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix([StageKey.ANALYZE], repeats=3),
            [_case()],
            ModelCatalog.builtin(),
        )
        assert estimate.model_costs[HAIKU] == pytest.approx(0.0042)

    def test_every_stage_uses_its_own_token_estimate(self) -> None:
        stages = [StageKey.ANALYZE, StageKey.SELECT]
        tokens_in = sum(STAGE_REQUIREMENTS[s].est_input_tokens for s in stages)
        tokens_out = sum(STAGE_REQUIREMENTS[s].est_output_tokens for s in stages)
        estimate = estimate_matrix_cost(
            _matrix(stages, models=[_unit_model("m")]),
            [_case()],
            ModelCatalog([_priced("p", "m", 1.0, 2.0)]),
        )
        assert estimate.model_costs["p/m"] == pytest.approx(
            (tokens_in * 1.0 + tokens_out * 2.0) / PER_MILLION
        )

    def test_a_case_restricted_to_review_skips_other_stages(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix([StageKey.ANALYZE]),
            [_case(stages=[StageKey.REVIEW])],
            ModelCatalog.builtin(),
        )
        assert estimate.model_costs[HAIKU] == 0.0

    def test_each_model_is_estimated_separately(self) -> None:
        catalog = ModelCatalog(
            [_priced("p", "cheap", 1.0, 1.0), _priced("p", "dear", 10.0, 10.0)]
        )
        estimate = estimate_matrix_cost(
            _matrix(
                [StageKey.ANALYZE], models=[_unit_model("cheap"), _unit_model("dear")]
            ),
            [_case()],
            catalog,
        )
        costs = estimate.model_costs
        assert costs["p/dear"] == pytest.approx(10 * costs["p/cheap"])  # type: ignore[operator]


class TestUnknownPrices:
    def test_an_unpriced_model_costs_none(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix([StageKey.ANALYZE]), [_case()], ModelCatalog([])
        )
        assert estimate.model_costs[HAIKU] is None

    def test_no_known_price_leaves_the_total_unknown(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix([StageKey.ANALYZE]), [_case()], ModelCatalog([])
        )
        assert estimate.total_usd is None

    def test_a_missing_price_makes_the_total_partial(self) -> None:
        catalog = ModelCatalog(
            [
                _priced("p", "m", 1.0, 1.0),
                _priced("anthropic", "claude-opus-5-5", 5.0, 25.0),
            ]
        )
        estimate = estimate_matrix_cost(
            _matrix(
                [StageKey.ANALYZE], models=[_unit_model("m"), _unit_model("unpriced")]
            ),
            [_case()],
            catalog,
        )
        assert estimate.is_partial is True

    def test_a_fully_priced_estimate_is_not_partial(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix([StageKey.ANALYZE]), [_case()], ModelCatalog.builtin()
        )
        assert estimate.is_partial is False


class TestJudgeCost:
    def _estimate(self, stage: StageKey, cases: list[EvalCase], **options: int):  # type: ignore[no-untyped-def]
        return estimate_matrix_cost(
            _matrix([stage], models=[_unit_model("m")], **options),
            cases,
            JUDGED_CATALOG,
        )

    def test_select_makes_one_judge_call_per_run(self) -> None:
        assert self._estimate(StageKey.SELECT, [_case()]).judge_calls == 1

    def test_tailor_makes_two_judge_calls_per_run(self) -> None:
        assert self._estimate(StageKey.TAILOR, [_case()]).judge_calls == 2

    def test_judge_calls_are_priced_at_the_judge_model(self) -> None:
        per_call = (JUDGE_INPUT_TOKENS * 5.0 + JUDGE_OUTPUT_TOKENS * 25.0) / PER_MILLION
        estimate = self._estimate(StageKey.TAILOR, [_case()])
        assert estimate.judge_cost_usd == pytest.approx(2 * per_call)

    def test_review_judges_only_cases_with_seeded_defects(self) -> None:
        probe = _case("probe", review_probe_defects=["a defect"])
        assert self._estimate(StageKey.REVIEW, [_case(), probe]).judge_calls == 1

    def test_judge_calls_scale_with_models_and_repeats(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix(
                [StageKey.SELECT],
                models=[_unit_model("m"), _unit_model("n")],
                repeats=2,
            ),
            [_case()],
            JUDGED_CATALOG,
        )
        assert estimate.judge_calls == 4

    def test_an_unpriced_judge_leaves_its_cost_unknown(self) -> None:
        estimate = estimate_matrix_cost(
            _matrix([StageKey.SELECT], models=[_unit_model("m")]),
            [_case()],
            ModelCatalog([_priced("p", "m", 0.0, 0.0)]),
        )
        assert estimate.judge_cost_usd is None

    def test_the_judge_is_named_in_the_estimate(self) -> None:
        assert self._estimate(StageKey.SELECT, [_case()]).judges == [
            "anthropic/claude-opus-5-5"
        ]


PANEL = [
    JudgeConfig(provider="anthropic", model="claude-opus-5-5"),
    JudgeConfig(provider="openai", model="gpt-6-astra"),
    JudgeConfig(provider="google", model="gemini-4-argon"),
]


class TestJudgePanelCost:
    def _estimate(self, **options: object) -> CostEstimate:
        matrix = MatrixConfig(
            run=RunSettings(stages=[StageKey.TAILOR]),
            judges=PANEL,
            reference=JUDGE,
            models=[MatrixModel(provider="openai", model="gpt-6-luna")],
        )
        return estimate_matrix_cost(
            matrix,
            [_case()],
            ModelCatalog.builtin(),
            **options,  # type: ignore[arg-type]
        )

    def _per_call(self, provider: str, model: str) -> float:
        price = ModelCatalog.builtin().price_for(model, provider=provider)
        assert price is not None
        return (JUDGE_INPUT_TOKENS * price[0] + JUDGE_OUTPUT_TOKENS * price[1]) / (
            PER_MILLION
        )

    def test_every_judge_makes_every_judge_call(self) -> None:
        estimate = self._estimate()
        assert estimate.judge_calls == 2
        assert list(estimate.judge_costs) == [j.label for j in PANEL]

    def test_each_judge_is_priced_at_its_own_model(self) -> None:
        estimate = self._estimate()
        assert estimate.judge_costs["openai/gpt-6-astra"] == pytest.approx(
            2 * self._per_call("openai", "gpt-6-astra")
        )

    def test_the_judge_cost_is_the_sum_over_the_panel(self) -> None:
        estimate = self._estimate()
        assert estimate.judge_cost_usd == pytest.approx(
            sum(2 * self._per_call(j.provider, j.model) for j in PANEL)
        )

    def test_the_total_includes_every_judge(self) -> None:
        estimate = self._estimate()
        model = estimate.model_costs["openai/gpt-6-luna"]
        assert model is not None and estimate.judge_cost_usd is not None
        assert estimate.total_usd == pytest.approx(model + estimate.judge_cost_usd)

    def test_costs_are_broken_down_by_provider(self) -> None:
        estimate = self._estimate()
        luna = estimate.model_costs["openai/gpt-6-luna"]
        astra = estimate.judge_costs["openai/gpt-6-astra"]
        assert luna is not None and astra is not None
        assert estimate.provider_costs["openai"] == pytest.approx(luna + astra)
        assert (
            estimate.provider_costs["google"]
            == estimate.judge_costs["google/gemini-4-argon"]
        )
        assert sorted(estimate.provider_costs) == ["anthropic", "google", "openai"]

    def test_the_provider_costs_add_up_to_the_total(self) -> None:
        estimate = self._estimate()
        assert sum(
            cost for cost in estimate.provider_costs.values() if cost is not None
        ) == pytest.approx(estimate.total_usd)

    def test_a_skipped_judge_is_left_out_and_named(self) -> None:
        reason = "no API key for provider 'openai' (set OPENAI_API_KEY)"
        estimate = self._estimate(skipped_judges={"openai/gpt-6-astra": reason})
        assert estimate.judges == ["anthropic/claude-opus-5-5", "google/gemini-4-argon"]
        assert "openai/gpt-6-astra" not in estimate.judge_costs
        assert estimate.skipped_judges == {"openai/gpt-6-astra": reason}


class TestNothingToRun:
    def test_a_matrix_with_no_models_costs_nothing(self) -> None:
        matrix = _matrix([StageKey.TAILOR]).model_copy(update={"models": []})
        estimate = estimate_matrix_cost(matrix, [_case()], ModelCatalog.builtin())
        assert (estimate.total_usd, estimate.is_partial) == (0.0, False)


class TestJudgeSkipped:
    """A judge without credentials makes no calls, so it costs nothing."""

    REASON = "no API key for provider 'anthropic' (set ANTHROPIC_API_KEY)"
    LABEL = "anthropic/claude-opus-5-5"

    def _estimate(self, stages: list[StageKey], reason: str | None) -> CostEstimate:
        return estimate_matrix_cost(
            _matrix(stages),
            [_case()],
            ModelCatalog.builtin(),
            skipped_judges={self.LABEL: reason} if reason else None,
        )

    def test_a_skipped_judge_makes_no_calls_and_costs_nothing(self) -> None:
        estimate = self._estimate([StageKey.TAILOR], self.REASON)
        assert (estimate.judges, estimate.judge_cost_usd) == ([], 0.0)

    def test_the_reason_is_reported(self) -> None:
        estimate = self._estimate([StageKey.TAILOR], self.REASON)
        assert estimate.skipped_judges == {self.LABEL: self.REASON}

    def test_the_total_leaves_the_judge_out(self) -> None:
        skipped = self._estimate([StageKey.TAILOR], self.REASON)
        priced = self._estimate([StageKey.TAILOR], None)
        assert skipped.total_usd is not None and priced.total_usd is not None
        assert skipped.total_usd < priced.total_usd
        assert skipped.total_usd == skipped.model_costs[HAIKU]

    def test_a_stage_without_judge_calls_has_nothing_to_skip(self) -> None:
        estimate = self._estimate([StageKey.ANALYZE], self.REASON)
        assert estimate.skipped_judges == {}

    def test_an_available_judge_is_priced_as_before(self) -> None:
        estimate = self._estimate([StageKey.TAILOR], None)
        assert estimate.judge_calls == 2
        assert estimate.skipped_judges == {}


MODELS = [
    MatrixModel(provider="anthropic", model="claude-opus-5-5"),
    MatrixModel(provider="anthropic", model="claude-haiku-5-5"),
    MatrixModel(provider="openai", model="gpt-6-astra"),
    MatrixModel(provider="openai", model="gpt-6-luna"),
    MatrixModel(provider="google", model="gemini-4-argon"),
    MatrixModel(provider="google", model="gemini-3.5-flash-lite"),
]


def _tournament(**settings: object) -> MatrixConfig:
    return MatrixConfig(
        run=RunSettings(stages=[StageKey.TAILOR], repeats=2),
        judges=PANEL,
        reference=JUDGE,
        models=MODELS,
        tournament=TournamentSettings(screening_cases=["one"], **settings),  # type: ignore[arg-type]
    )


class TestTournamentEstimate:
    cases = (_case("one"), _case("two"), _case("three"))

    def test_screening_runs_every_model_on_the_subset_once(self) -> None:
        estimate = estimate_tournament_cost(
            _tournament(), list(self.cases), ModelCatalog.builtin()
        )
        assert estimate.screening.runs_per_model == 1
        assert set(estimate.screening.model_costs) == {m.label for m in MODELS}

    def test_screening_asks_one_judge_per_model(self) -> None:
        estimate = estimate_tournament_cost(
            _tournament(), list(self.cases), ModelCatalog.builtin()
        )
        calls = estimate.screening.judge_call_counts
        assert sum(calls.values()) == len(MODELS) * 2  # tailor: two judge calls

    def test_the_screening_judge_is_never_the_models_own_provider(self) -> None:
        estimate = estimate_tournament_cost(
            _tournament(), list(self.cases), ModelCatalog.builtin()
        )
        # two Anthropic models go to Google, four others to Anthropic's judge
        assert estimate.screening.judge_call_counts == {
            "anthropic/claude-opus-5-5": 8,
            "google/gemini-4-argon": 4,
        }

    def test_the_finals_run_the_assumed_survivors_on_every_case(self) -> None:
        estimate = estimate_tournament_cost(
            _tournament(), list(self.cases), ModelCatalog.builtin()
        )
        assert estimate.finals.runs_per_model == 3 * 2
        assert set(estimate.finals.model_costs) == {
            "anthropic/claude-opus-5-5",
            "openai/gpt-6-astra",
            "google/gemini-4-argon",
        }
        assert estimate.finals.judge_calls == 3 * 3 * 2 * 2

    def test_the_worst_case_keeps_every_model(self) -> None:
        estimate = estimate_tournament_cost(
            _tournament(), list(self.cases), ModelCatalog.builtin()
        )
        assert set(estimate.finals_worst_case.model_costs) == {m.label for m in MODELS}

    def test_the_total_is_screening_plus_finals(self) -> None:
        estimate = estimate_tournament_cost(
            _tournament(), list(self.cases), ModelCatalog.builtin()
        )
        assert estimate.screening.total_usd is not None
        assert estimate.finals.total_usd is not None
        assert estimate.total_usd == pytest.approx(
            estimate.screening.total_usd + estimate.finals.total_usd
        )


class TestAssumedSurvivors:
    def test_it_is_the_dearest_model_of_each_provider(self) -> None:
        labels = [
            m.label
            for m in assumed_survivors(
                MODELS, TournamentSettings(), ModelCatalog.builtin()
            )
        ]
        assert labels == [
            "anthropic/claude-opus-5-5",
            "openai/gpt-6-astra",
            "google/gemini-4-argon",
        ]

    def test_it_fills_up_to_the_top_count_with_the_next_dearest(self) -> None:
        survivors = assumed_survivors(
            MODELS, TournamentSettings(keep_top=4), ModelCatalog.builtin()
        )
        assert [m.label for m in survivors][3:] == ["google/gemini-3.5-flash-lite"]


class TestCachingEstimate:
    """Judge calls of one case share a cached prefix across models and repeats."""

    def _matrix(self, provider: str, model: str, **caching: object) -> MatrixConfig:
        return MatrixConfig(
            run=RunSettings(stages=[StageKey.SELECT], repeats=2),
            judges=[JudgeConfig(provider=provider, model=model)],
            reference=JUDGE,
            models=[_unit_model("m"), _unit_model("n")],
            caching=CachingSettings(enabled=True, **caching),  # type: ignore[arg-type]
        )

    def _cost(self, matrix: MatrixConfig) -> float:
        catalog = ModelCatalog(
            [
                _priced("p", "m", 0.0, 0.0),
                _priced("p", "n", 0.0, 0.0),
                _priced("anthropic", "opus", 1.0, 0.0),
                _priced("openai", "astra", 1.0, 0.0),
            ]
        )
        cost = estimate_matrix_cost(matrix, [_case()], catalog).judge_cost_usd
        assert cost is not None
        return cost

    def test_without_caching_every_prompt_token_is_full_price(self) -> None:
        matrix = self._matrix("anthropic", "opus").model_copy(
            update={"caching": CachingSettings(enabled=False)}
        )
        assert self._cost(matrix) == pytest.approx(4 * JUDGE_INPUT_TOKENS / PER_MILLION)

    def test_anthropic_writes_the_prefix_once_and_reads_it_after(self) -> None:
        cost = self._cost(
            self._matrix(
                "anthropic", "opus", judge_prefix_share=0.5, estimated_hit_rate=1.0
            )
        )
        prefix, rest = 3000, 3000
        # 4 calls, 1 distinct prefix: 1 write at 1.25x, 3 reads at 0.1x
        expected = (prefix * 1.25 + 3 * prefix * 0.1 + 4 * rest) / PER_MILLION
        assert cost == pytest.approx(expected)

    def test_openai_reads_at_its_multiplier_with_no_write_premium(self) -> None:
        cost = self._cost(
            self._matrix(
                "openai", "astra", judge_prefix_share=0.5, estimated_hit_rate=1.0
            )
        )
        expected = (3000 + 3 * 3000 * 0.5 + 4 * 3000) / PER_MILLION
        assert cost == pytest.approx(expected)

    def test_the_hit_rate_scales_the_reads(self) -> None:
        full = self._cost(self._matrix("openai", "astra", estimated_hit_rate=1.0))
        none = self._cost(self._matrix("openai", "astra", estimated_hit_rate=0.0))
        half = self._cost(self._matrix("openai", "astra", estimated_hit_rate=0.5))
        assert half == pytest.approx((full + none) / 2)
