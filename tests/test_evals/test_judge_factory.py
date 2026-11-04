"""Tests for creating the judge and deciding whether it can run (REQ-EV-20)."""

from collections.abc import Callable

import pytest
from dynaconf import Dynaconf

from evals.harness.judge_factory import (
    create_judge,
    judge_unavailable_reason,
    split_judges,
)
from evals.models.judge_config import JudgeConfig
from mkcv.adapters.factory import create_provider_registry
from mkcv.adapters.llm.provider_registry import ProviderRegistry
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.exceptions.configuration import ConfigurationError
from mkcv.core.ports.llm import LLMPort

CLAUDE = JudgeConfig(provider="anthropic", model="claude-opus-5-5")
STUB = JudgeConfig(provider="stub", model="stub-model")


@pytest.fixture
def registry(make_settings: Callable[..., Dynaconf]) -> ProviderRegistry:
    return create_provider_registry(make_settings())


class TestAvailability:
    def test_a_judge_without_a_key_is_unavailable(
        self, registry: ProviderRegistry
    ) -> None:
        assert judge_unavailable_reason(registry, CLAUDE) == (
            "no API key for provider 'anthropic' (set ANTHROPIC_API_KEY, or api_key in "
            "[default.providers.anthropic] in ~/.config/mkcv/settings.toml)"
        )

    def test_a_key_in_the_environment_makes_it_available(
        self, registry: ProviderRegistry, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        assert judge_unavailable_reason(registry, CLAUDE) is None

    def test_a_provider_that_needs_no_key_is_available(
        self, registry: ProviderRegistry
    ) -> None:
        assert judge_unavailable_reason(registry, STUB) is None

    def test_an_unknown_provider_is_a_configuration_error(
        self, registry: ProviderRegistry
    ) -> None:
        with pytest.raises(ConfigurationError, match="Unknown LLM provider 'nope'"):
            judge_unavailable_reason(registry, JudgeConfig(provider="nope", model="m"))


class TestCreation:
    def test_it_returns_the_providers_adapter_and_the_judge_model(
        self,
        registry: ProviderRegistry,
        install_adapter: Callable[[LLMPort], LLMPort],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        adapter = install_adapter(StubLLMAdapter())
        assert create_judge(registry, CLAUDE) == (adapter, "claude-opus-5-5")

    def test_the_adapter_is_asked_for_by_provider_name(
        self, registry: ProviderRegistry, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        asked: list[str] = []

        def create(self: ProviderRegistry, name: str, **_: object) -> LLMPort:
            asked.append(name)
            return StubLLMAdapter()

        monkeypatch.setattr(ProviderRegistry, "create_adapter", create)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        create_judge(registry, CLAUDE)
        assert asked == ["anthropic"]

    def test_a_provider_without_a_key_is_refused_instead_of_given_a_stub(
        self, registry: ProviderRegistry
    ) -> None:
        with pytest.raises(ConfigurationError, match="no API key"):
            create_judge(registry, CLAUDE)


class TestSplitJudges:
    def test_judges_with_credentials_run_in_panel_order(
        self, registry: ProviderRegistry, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        runnable, skipped = split_judges(registry, [STUB, CLAUDE])
        assert (runnable, skipped) == ([STUB, CLAUDE], {})

    def test_a_judge_without_credentials_is_skipped_with_its_reason(
        self, registry: ProviderRegistry
    ) -> None:
        runnable, skipped = split_judges(registry, [CLAUDE, STUB])
        assert runnable == [STUB]
        assert skipped == {
            "anthropic/claude-opus-5-5": (
                "no API key for provider 'anthropic' (set ANTHROPIC_API_KEY)"
            )
        }

    def test_an_unknown_provider_is_a_configuration_error(
        self, registry: ProviderRegistry
    ) -> None:
        with pytest.raises(ConfigurationError):
            split_judges(registry, [JudgeConfig(provider="nope", model="m")])
