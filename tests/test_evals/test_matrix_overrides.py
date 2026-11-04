"""Tests for command-line overrides of the matrix and credential splitting."""

from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest
from dynaconf import Dynaconf
from google.auth.exceptions import DefaultCredentialsError

from evals.harness.credentials import split_by_credentials
from evals.models.judge_config import JudgeConfig
from evals.models.matrix_config import MatrixConfig
from evals.models.matrix_model import MatrixModel
from evals.models.matrix_overrides import MatrixOverrides
from evals.models.recommendation_settings import RecommendationSettings
from evals.models.run_settings import RunSettings
from evals.stages import EVALUATED_STAGES
from mkcv.adapters.factory import create_provider_registry
from mkcv.core.models.stage_key import StageKey

JUDGE = JudgeConfig(provider="anthropic", model="claude-opus-5-5")
HAIKU = MatrixModel(provider="anthropic", model="claude-haiku-5-5", temperature=0.4)
SOL = MatrixModel(provider="openai", model="gpt-6.1-sol")


def _matrix() -> MatrixConfig:
    return MatrixConfig(
        run=RunSettings(concurrency=3, repeats=2),
        judge=JUDGE,
        reference=JUDGE,
        models=[HAIKU, SOL],
    )


class TestMatrixOverrides:
    def test_no_overrides_leave_the_matrix_unchanged(self) -> None:
        assert MatrixOverrides().apply(_matrix()) == _matrix()

    def test_stages_replace_the_run_stages(self) -> None:
        result = MatrixOverrides(stages=["analyze", "review"]).apply(_matrix())
        assert result.run.stages == [StageKey.ANALYZE, StageKey.REVIEW]

    def test_an_unknown_stage_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="polish"):
            MatrixOverrides(stages=["polish"]).apply(_matrix())

    def test_a_non_pipeline_stage_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="not stages the harness evaluates"):
            MatrixOverrides(stages=["kb"]).apply(_matrix())

    def test_cases_replace_the_run_cases(self) -> None:
        result = MatrixOverrides(cases=["a", "b"]).apply(_matrix())
        assert result.run.cases == ["a", "b"]

    def test_concurrency_replaces_the_run_concurrency(self) -> None:
        assert MatrixOverrides(concurrency=1).apply(_matrix()).run.concurrency == 1

    def test_concurrency_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="concurrency"):
            MatrixOverrides(concurrency=0).apply(_matrix())

    def test_other_run_settings_are_kept(self) -> None:
        result = MatrixOverrides(concurrency=1).apply(_matrix())
        assert result.run.repeats == 2
        assert tuple(result.run.stages) == EVALUATED_STAGES

    def test_models_replace_the_matrix_models(self) -> None:
        result = MatrixOverrides(models=["stub:stub-model"]).apply(_matrix())
        assert [m.label for m in result.models] == ["stub/stub-model"]

    def test_a_listed_matrix_model_keeps_its_temperature(self) -> None:
        result = MatrixOverrides(models=["anthropic:claude-haiku-5-5"]).apply(_matrix())
        assert result.models == [HAIKU]

    def test_a_model_id_may_contain_colons(self) -> None:
        result = MatrixOverrides(models=["ollama:llama3.1:8b"]).apply(_matrix())
        assert (result.models[0].provider, result.models[0].model) == (
            "ollama",
            "llama3.1:8b",
        )

    def test_a_model_without_a_provider_is_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"--models.*provider:model.*gpt-6"):
            MatrixOverrides(models=["gpt-6"]).apply(_matrix())

    def test_the_judge_is_replaced(self) -> None:
        result = MatrixOverrides(judges=["openai:gpt-6.1-sol"]).apply(_matrix())
        assert result.panel == [JudgeConfig(provider="openai", model="gpt-6.1-sol")]

    def test_several_judges_make_a_panel(self) -> None:
        result = MatrixOverrides(
            judges=["openai:gpt-6-astra", "google:gemini-4-argon"]
        ).apply(_matrix())
        assert [j.label for j in result.panel] == [
            "openai/gpt-6-astra",
            "google/gemini-4-argon",
        ]

    def test_the_override_replaces_a_matrix_panel(self) -> None:
        matrix = MatrixConfig(
            judges=[JUDGE, JudgeConfig(provider="google", model="gemini-4-argon")],
            reference=JUDGE,
            models=[HAIKU],
        )
        result = MatrixOverrides(judges=["openai:gpt-6-astra"]).apply(matrix)
        assert [j.label for j in result.panel] == ["openai/gpt-6-astra"]

    def test_a_judge_without_a_colon_is_a_usage_error(self) -> None:
        with pytest.raises(ValueError, match=r"--judge expects provider:model"):
            MatrixOverrides(judges=["gpt-6.1-sol"]).apply(_matrix())

    @pytest.mark.parametrize("value", [":model", "provider:"])
    def test_a_judge_with_an_empty_side_is_a_usage_error(self, value: str) -> None:
        with pytest.raises(ValueError, match="--judge expects provider:model"):
            MatrixOverrides(judges=[value]).apply(_matrix())

    def test_the_reference_model_is_not_touched_by_the_judge_override(self) -> None:
        result = MatrixOverrides(judges=["openai:gpt-6.1-sol"]).apply(_matrix())
        assert result.reference == JUDGE

    def test_the_recommendation_settings_are_kept(self) -> None:
        settings = RecommendationSettings(tie_epsilon=0.02)
        matrix = _matrix().model_copy(update={"recommendation": settings})
        assert MatrixOverrides(cases=["a"]).apply(matrix).recommendation == settings


class TestSplitByCredentials:
    def test_models_without_a_key_are_skipped_and_named(
        self, make_settings: Callable[..., Dynaconf]
    ) -> None:
        registry = create_provider_registry(make_settings())
        runnable, skipped = split_by_credentials(registry, [HAIKU, SOL])
        assert runnable == []
        assert skipped[0].startswith("anthropic/claude-haiku-5-5: ")
        assert "provider 'anthropic'" in skipped[0]
        assert "ANTHROPIC_API_KEY" in skipped[0]

    def test_a_model_with_a_key_runs(
        self,
        make_settings: Callable[..., Dynaconf],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        registry = create_provider_registry(make_settings())
        runnable, skipped = split_by_credentials(registry, [HAIKU, SOL])
        assert runnable == [SOL]
        assert len(skipped) == 1

    def test_the_stub_and_local_providers_need_no_key(
        self, make_settings: Callable[..., Dynaconf]
    ) -> None:
        registry = create_provider_registry(make_settings())
        models = [
            MatrixModel(provider="stub", model="stub-model"),
            MatrixModel(provider="ollama", model="llama3.1:8b"),
        ]
        assert split_by_credentials(registry, models) == (models, [])

    def test_a_key_in_the_config_file_counts(
        self, make_settings: Callable[..., Dynaconf]
    ) -> None:
        settings = make_settings('[default.providers.openai]\napi_key = "sk-file"\n')
        registry = create_provider_registry(settings)
        assert split_by_credentials(registry, [SOL]) == ([SOL], [])

    def test_the_order_of_models_is_kept(
        self,
        make_settings: Callable[..., Dynaconf],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
        registry = create_provider_registry(make_settings())
        assert split_by_credentials(registry, [SOL, HAIKU])[0] == [SOL, HAIKU]

    def test_an_unknown_provider_is_a_configuration_error(
        self, make_settings: Callable[..., Dynaconf]
    ) -> None:
        from mkcv.core.exceptions.configuration import ConfigurationError

        registry = create_provider_registry(make_settings())
        with pytest.raises(ConfigurationError, match="Unknown LLM provider 'nowhere'"):
            split_by_credentials(registry, [MatrixModel(provider="nowhere", model="m")])


GEMINI = MatrixModel(provider="google", model="gemini-3.8-flash")
VERTEX_SETTINGS = "[default.providers.google]\nvertexai = true\n"


class TestSplitByCredentialsWithVertex:
    def test_google_with_adc_is_runnable_without_a_key(
        self, make_settings: Callable[..., Dynaconf]
    ) -> None:
        registry = create_provider_registry(make_settings(VERTEX_SETTINGS))
        with patch("google.auth.default", return_value=(MagicMock(), "p")):
            assert split_by_credentials(registry, [GEMINI]) == ([GEMINI], [])

    def test_google_without_adc_is_skipped_with_the_login_hint(
        self, make_settings: Callable[..., Dynaconf]
    ) -> None:
        registry = create_provider_registry(make_settings(VERTEX_SETTINGS))
        with patch("google.auth.default", side_effect=DefaultCredentialsError("x")):
            runnable, skipped = split_by_credentials(registry, [GEMINI])
        assert runnable == []
        assert "gcloud auth application-default login" in skipped[0]

    def test_google_without_a_key_mentions_the_adc_alternative(
        self, make_settings: Callable[..., Dynaconf]
    ) -> None:
        registry = create_provider_registry(make_settings())
        _, skipped = split_by_credentials(registry, [GEMINI])
        assert "GEMINI_API_KEY" in skipped[0]
        assert "Application Default Credentials" in skipped[0]
