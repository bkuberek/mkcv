"""Tests for StageResolver (REQ-SR-1 to SR-7, design section 6.5)."""

import logging
from pathlib import Path
from typing import Any

import pytest
from dynaconf import Dynaconf
from pydantic import ValidationError

import mkcv
from mkcv.adapters.llm.model_catalog_loader import load_model_catalog
from mkcv.adapters.llm.provider_registry import ProviderRegistry
from mkcv.adapters.llm.resolution_request import ResolutionRequest
from mkcv.adapters.llm.resolved_stages import ResolvedStages
from mkcv.adapters.llm.stage_resolver import DEFAULT_PROVIDER, StageResolver
from mkcv.core.exceptions.configuration import ConfigurationError
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.stage_config import StageConfig
from mkcv.core.models.stage_key import (
    COVER_LETTER_STAGES,
    PIPELINE_STAGES,
    StageKey,
)

BUNDLED_SETTINGS = Path(mkcv.__file__).resolve().parent / "config" / "settings.toml"

_KEY_VARIABLES = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
)

type Row = tuple[str, str, float, str]

# provider, model, temperature, source for each pipeline stage under "standard".
STANDARD_ROWS: dict[StageKey, Row] = {
    StageKey.ANALYZE: ("anthropic", "claude-haiku-5-5", 0.2, "profile"),
    StageKey.SELECT: ("anthropic", "claude-opus-5-5", 0.3, "profile"),
    StageKey.TAILOR: ("anthropic", "claude-opus-5-5", 0.5, "profile"),
    StageKey.STRUCTURE: ("anthropic", "claude-sonnet-5-5", 0.1, "profile"),
    StageKey.REVIEW: ("anthropic", "claude-opus-5-5", 0.3, "profile"),
}

GROQ_PROVIDER = """
[default.providers.groq]
type = "openai-compatible"
base_url = "https://api.groq.com/openai/v1"
api_key_env = "GROQ_API_KEY"
"""


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in _KEY_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def _config(tmp_path: Path, *layers: str) -> Dynaconf:
    paths = [str(BUNDLED_SETTINGS)]
    for index, text in enumerate(layers):
        path = tmp_path / f"layer{index}.toml"
        path.write_text(text)
        paths.append(str(path))
    return Dynaconf(
        settings_files=paths,
        environments=True,
        default_env="default",
        merge_enabled=True,
    )


def _resolve(
    tmp_path: Path,
    stages: tuple[StageKey, ...] = PIPELINE_STAGES,
    *layers: str,
    **request: Any,
) -> ResolvedStages:
    config = _config(tmp_path, *layers)
    registry = ProviderRegistry.from_config(config, load_model_catalog(config))
    return StageResolver(config, registry).resolve(stages, ResolutionRequest(**request))


def _rows(resolved: ResolvedStages) -> dict[StageKey, Row]:
    return {
        stage: (a.provider, a.model, a.temperature, a.source)
        for stage, a in resolved.assignments.items()
    }


def _row(resolved: ResolvedStages, stage: StageKey) -> Row:
    return _rows(resolved)[stage]


class TestDefaultsReproduceToday:
    """REQ-SR-1."""

    def test_standard_preset_gives_the_smart_claude_mix(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, preset_name="standard")
        assert _rows(resolved) == STANDARD_ROWS

    def test_concise_preset_runs_every_stage_on_haiku(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, preset_name="concise")
        assert {(r[0], r[1]) for r in _rows(resolved).values()} == {
            ("anthropic", "claude-haiku-5-5")
        }

    def test_concise_preset_keeps_each_stages_temperature(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, preset_name="concise")
        assert [r[2] for r in _rows(resolved).values()] == [0.2, 0.3, 0.5, 0.1, 0.3]

    def test_cover_letter_stages(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, COVER_LETTER_STAGES)
        assert _rows(resolved) == {
            StageKey.COVER_LETTER_GENERATE: (
                "anthropic",
                "claude-opus-5-5",
                0.6,
                "profile",
            ),
            StageKey.COVER_LETTER_REVIEW: (
                "anthropic",
                "claude-haiku-5-5",
                0.2,
                "profile",
            ),
        }

    def test_kb_stage(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, (StageKey.KB,))
        assert _row(resolved, StageKey.KB) == (
            "anthropic",
            "claude-sonnet-5-5",
            0.3,
            "profile",
        )

    def test_validate_stage(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, (StageKey.VALIDATE,))
        assert _row(resolved, StageKey.VALIDATE) == (
            "anthropic",
            "claude-sonnet-5-5",
            0.3,
            "profile",
        )

    def test_profile_and_source_describe_the_default(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, preset_name="standard")
        assert resolved.profile is not None
        assert (resolved.profile.name, resolved.profile_source) == (
            "anthropic",
            "default",
        )

    def test_concise_selects_the_economy_variant(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, preset_name="concise")
        assert resolved.profile is not None
        assert resolved.profile.name == "anthropic-economy"

    def test_preset_name_is_recorded(self, tmp_path: Path) -> None:
        assert _resolve(tmp_path, preset_name="concise").preset_name == "concise"

    def test_stages_resolve_in_the_order_given(self, tmp_path: Path) -> None:
        stages = (StageKey.REVIEW, StageKey.ANALYZE)
        assert list(_resolve(tmp_path, stages).assignments) == list(stages)

    def test_assignments_carry_the_provider_kind(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, (StageKey.KB,))
        assert resolved.assignments[StageKey.KB].provider_kind is ProviderKind.ANTHROPIC

    def test_default_provider_constant(self) -> None:
        assert DEFAULT_PROVIDER == "anthropic"


class TestPerStageConfigBeatsTheProfile:
    """REQ-SR-2."""

    TAILOR_ON_OPENAI = """
[default.pipeline.stages.tailor]
provider = "openai"
model = "gpt-6.1-sol"
"""

    def test_configured_stage_uses_its_provider_and_model(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, PIPELINE_STAGES, self.TAILOR_ON_OPENAI)
        assert _row(resolved, StageKey.TAILOR) == (
            "openai",
            "gpt-6.1-sol",
            0.5,
            "config",
        )

    def test_other_stages_are_unchanged(self, tmp_path: Path) -> None:
        resolved = _resolve(
            tmp_path, PIPELINE_STAGES, self.TAILOR_ON_OPENAI, preset_name="standard"
        )
        rows = _rows(resolved)
        del rows[StageKey.TAILOR]
        assert rows == {
            k: v for k, v in STANDARD_ROWS.items() if k is not StageKey.TAILOR
        }

    def test_config_beats_the_preset_it_used_to_lose_to(self, tmp_path: Path) -> None:
        resolved = _resolve(
            tmp_path, PIPELINE_STAGES, self.TAILOR_ON_OPENAI, preset_name="concise"
        )
        assert _row(resolved, StageKey.TAILOR)[:2] == ("openai", "gpt-6.1-sol")

    def test_model_alone_infers_the_provider_from_the_catalog(
        self, tmp_path: Path
    ) -> None:
        layer = '[default.pipeline.stages.tailor]\nmodel = "gpt-6.1-sol"\n'
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer)
        assert _row(resolved, StageKey.TAILOR)[:2] == ("openai", "gpt-6.1-sol")

    def test_unknown_model_alone_uses_the_active_profiles_provider(
        self, tmp_path: Path
    ) -> None:
        layer = '[default.pipeline.stages.tailor]\nmodel = "my-finetune"\n'
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer)
        assert _row(resolved, StageKey.TAILOR)[:2] == ("anthropic", "my-finetune")

    def test_unknown_model_alone_follows_a_config_selected_profile(
        self, tmp_path: Path
    ) -> None:
        layer = (
            '[default.pipeline]\nmodel_profile = "google"\n'
            '[default.pipeline.stages.tailor]\nmodel = "my-finetune"\n'
        )
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer)
        assert _row(resolved, StageKey.TAILOR)[:2] == ("google", "my-finetune")

    def test_unknown_model_alone_follows_the_default_provider_without_a_profile(
        self, tmp_path: Path
    ) -> None:
        layer = (
            GROQ_PROVIDER
            + '[default.pipeline]\nprovider = "groq"\n'
            + '[default.pipeline.stages.tailor]\nmodel = "llama-3.3-70b-versatile"\n'
            + "".join(
                f'[default.pipeline.stages.{s.value}]\nprovider = "groq"\n'
                f'model = "llama-3.3-70b-versatile"\n'
                for s in PIPELINE_STAGES
                if s is not StageKey.TAILOR
            )
        )
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer)
        assert _row(resolved, StageKey.TAILOR)[0] == "groq"

    def test_provider_alone_uses_that_providers_recommended_model(
        self, tmp_path: Path
    ) -> None:
        layer = '[default.pipeline.stages.select]\nprovider = "google"\n'
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer)
        assert _row(resolved, StageKey.SELECT) == (
            "google",
            "gemini-4-argon",
            0.3,
            "config",
        )

    def test_provider_alone_follows_the_presets_economy_flag(
        self, tmp_path: Path
    ) -> None:
        layer = '[default.pipeline.stages.select]\nprovider = "google"\n'
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer, preset_name="concise")
        assert _row(resolved, StageKey.SELECT)[:2] == ("google", "gemini-3.8-flash")

    def test_provider_alone_without_a_profile_is_an_error(self, tmp_path: Path) -> None:
        layer = GROQ_PROVIDER + '[default.pipeline.stages.select]\nprovider = "groq"\n'
        with pytest.raises(
            ConfigurationError, match=r"stage 'select' with provider 'groq'"
        ):
            _resolve(tmp_path, PIPELINE_STAGES, layer)

    def test_configured_temperature_applies_to_profile_models(
        self, tmp_path: Path
    ) -> None:
        layer = "[default.pipeline.stages.tailor]\ntemperature = 0.9\n"
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer)
        assert _row(resolved, StageKey.TAILOR) == (
            "anthropic",
            "claude-opus-5-5",
            0.9,
            "profile",
        )

    def test_legacy_provider_and_model_keys_still_work(self, tmp_path: Path) -> None:
        layer = (
            '[default.pipeline.stages.analyze]\nprovider = "anthropic"\n'
            'model = "claude-sonnet-5-5"\ntemperature = 0.2\n'
        )
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer)
        assert _row(resolved, StageKey.ANALYZE) == (
            "anthropic",
            "claude-sonnet-5-5",
            0.2,
            "config",
        )

    def test_cover_letter_stage_config_is_read_from_its_own_section(
        self, tmp_path: Path
    ) -> None:
        layer = '[default.cover_letter.stages.generate]\nmodel = "gpt-6-astra"\n'
        resolved = _resolve(tmp_path, COVER_LETTER_STAGES, layer)
        assert _row(resolved, StageKey.COVER_LETTER_GENERATE)[:2] == (
            "openai",
            "gpt-6-astra",
        )

    def test_kb_and_validate_read_their_top_level_sections(
        self, tmp_path: Path
    ) -> None:
        layer = (
            '[default.kb]\nprovider = "google"\n'
            '[default.validate]\nmodel = "gpt-6.1-terra"\n'
        )
        resolved = _resolve(tmp_path, (StageKey.KB, StageKey.VALIDATE), layer)
        assert [_row(resolved, s)[:2] for s in (StageKey.KB, StageKey.VALIDATE)] == [
            ("google", "gemini-3.8-flash"),
            ("openai", "gpt-6.1-terra"),
        ]

    def test_unknown_provider_in_a_stage_is_a_configuration_error(
        self, tmp_path: Path
    ) -> None:
        layer = '[default.pipeline.stages.tailor]\nprovider = "nope"\nmodel = "m"\n'
        with pytest.raises(ConfigurationError, match="Unknown LLM provider 'nope'"):
            _resolve(tmp_path, PIPELINE_STAGES, layer)


class TestConfigLevelProfileAndProvider:
    """REQ-SR-3."""

    def test_model_profile_in_config_selects_that_profile(self, tmp_path: Path) -> None:
        layer = '[default.pipeline]\nmodel_profile = "openai"\n'
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer)
        assert [r[1] for r in _rows(resolved).values()] == [
            "gpt-6-luna",
            "gpt-6.1-sol",
            "gpt-6-astra",
            "gpt-6.1-terra",
            "gpt-6.1-sol",
        ]
        assert {r[0] for r in _rows(resolved).values()} == {"openai"}

    def test_profile_source_is_config(self, tmp_path: Path) -> None:
        layer = '[default.pipeline]\nmodel_profile = "openai"\n'
        assert _resolve(tmp_path, PIPELINE_STAGES, layer).profile_source == "config"

    def test_concise_preset_switches_to_the_economy_profile(
        self, tmp_path: Path
    ) -> None:
        layer = '[default.pipeline]\nmodel_profile = "openai"\n'
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer, preset_name="concise")
        assert resolved.profile is not None
        assert resolved.profile.name == "openai-economy"

    def test_an_explicit_economy_profile_is_kept_by_a_regular_preset(
        self, tmp_path: Path
    ) -> None:
        layer = '[default.pipeline]\nmodel_profile = "openai-economy"\n'
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer, preset_name="standard")
        assert resolved.profile is not None
        assert resolved.profile.name == "openai-economy"

    def test_profile_without_an_economy_variant_is_kept_for_economy_presets(
        self, tmp_path: Path
    ) -> None:
        layer = '[default.pipeline]\nmodel_profile = "local"\n'
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer, preset_name="concise")
        assert {r[0] for r in _rows(resolved).values()} == {"ollama"}

    def test_provider_in_config_selects_that_providers_profile(
        self, tmp_path: Path
    ) -> None:
        layer = '[default.pipeline]\nprovider = "google"\n'
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer)
        assert resolved.profile is not None
        assert (resolved.profile.name, resolved.profile_source) == ("google", "config")

    def test_unknown_profile_in_config_is_a_configuration_error(
        self, tmp_path: Path
    ) -> None:
        layer = '[default.pipeline]\nmodel_profile = "nope"\n'
        with pytest.raises(ConfigurationError, match="Unknown model profile 'nope'"):
            _resolve(tmp_path, PIPELINE_STAGES, layer)

    def test_unknown_profile_error_lists_the_available_profiles(
        self, tmp_path: Path
    ) -> None:
        layer = '[default.pipeline]\nmodel_profile = "nope"\n'
        with pytest.raises(ConfigurationError) as caught:
            _resolve(tmp_path, PIPELINE_STAGES, layer)
        assert (
            "Available: anthropic, anthropic-economy, google, google-economy, "
            "local, openai, openai-economy" in str(caught.value)
        )

    def test_unknown_provider_in_config_is_a_configuration_error(
        self, tmp_path: Path
    ) -> None:
        layer = '[default.pipeline]\nprovider = "nope"\n'
        with pytest.raises(ConfigurationError, match="Unknown LLM provider 'nope'"):
            _resolve(tmp_path, PIPELINE_STAGES, layer)

    def test_a_config_provider_without_a_profile_needs_explicit_models(
        self, tmp_path: Path
    ) -> None:
        layer = GROQ_PROVIDER + '[default.pipeline]\nprovider = "groq"\n'
        with pytest.raises(ConfigurationError, match=r"^Cannot resolve models:"):
            _resolve(tmp_path, PIPELINE_STAGES, layer)

    def test_a_configured_model_profile_beats_a_configured_provider(
        self, tmp_path: Path
    ) -> None:
        layer = '[default.pipeline]\nmodel_profile = "openai"\nprovider = "google"\n'
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer)
        assert {r[0] for r in _rows(resolved).values()} == {"openai"}


class TestCliModelProfile:
    """REQ-SR-4."""

    TAILOR_ON_OPENAI = TestPerStageConfigBeatsTheProfile.TAILOR_ON_OPENAI

    def test_per_stage_config_is_ignored(self, tmp_path: Path) -> None:
        resolved = _resolve(
            tmp_path, PIPELINE_STAGES, self.TAILOR_ON_OPENAI, model_profile="google"
        )
        assert [r[:2] for r in _rows(resolved).values()] == [
            ("google", "gemini-3.5-flash-lite"),
            ("google", "gemini-4-argon"),
            ("google", "gemini-4-argon"),
            ("google", "gemini-3.8-flash"),
            ("google", "gemini-4-argon"),
        ]

    def test_every_source_is_cli(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, model_profile="google")
        assert {r[3] for r in _rows(resolved).values()} == {"cli"}

    def test_profile_source_is_cli(self, tmp_path: Path) -> None:
        assert _resolve(tmp_path, model_profile="google").profile_source == "cli"

    def test_beats_a_configured_profile(self, tmp_path: Path) -> None:
        layer = '[default.pipeline]\nmodel_profile = "openai"\n'
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer, model_profile="google")
        assert {r[0] for r in _rows(resolved).values()} == {"google"}

    def test_cannot_be_combined_with_a_provider(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="cannot be used together"):
            _resolve(tmp_path, model_profile="google", provider_override="openai")

    def test_unknown_profile_is_a_configuration_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="Unknown model profile 'nope'"):
            _resolve(tmp_path, model_profile="nope")

    def test_an_explicit_profile_is_not_swapped_for_the_economy_variant(
        self, tmp_path: Path
    ) -> None:
        resolved = _resolve(tmp_path, model_profile="openai", preset_name="concise")
        assert resolved.profile is not None
        assert resolved.profile.name == "openai"

    def test_an_economy_profile_resolves_the_cover_letter_stages_too(
        self, tmp_path: Path
    ) -> None:
        resolved = _resolve(
            tmp_path, COVER_LETTER_STAGES, model_profile="openai-economy"
        )
        assert _row(resolved, StageKey.COVER_LETTER_GENERATE)[:2] == (
            "openai",
            "gpt-6-astra",
        )

    def test_the_profile_wins_over_the_presets_provider(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, model_profile="google", preset_name="budget")
        assert {r[0] for r in _rows(resolved).values()} == {"google"}


class TestCliProvider:
    """REQ-SR-5."""

    def test_every_stage_uses_the_providers_recommended_models(
        self, tmp_path: Path
    ) -> None:
        resolved = _resolve(tmp_path, provider_override="openai")
        assert [r[:2] for r in _rows(resolved).values()] == [
            ("openai", "gpt-6-luna"),
            ("openai", "gpt-6.1-sol"),
            ("openai", "gpt-6-astra"),
            ("openai", "gpt-6.1-terra"),
            ("openai", "gpt-6.1-sol"),
        ]

    def test_every_source_is_cli(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, provider_override="openai")
        assert {r[3] for r in _rows(resolved).values()} == {"cli"}

    def test_profile_source_is_cli(self, tmp_path: Path) -> None:
        assert _resolve(tmp_path, provider_override="openai").profile_source == "cli"

    def test_config_for_the_same_provider_is_kept(self, tmp_path: Path) -> None:
        layer = (
            '[default.pipeline.stages.tailor]\nprovider = "openai"\n'
            'model = "gpt-6-luna"\n'
        )
        resolved = _resolve(
            tmp_path, PIPELINE_STAGES, layer, provider_override="openai"
        )
        assert _row(resolved, StageKey.TAILOR) == (
            "openai",
            "gpt-6-luna",
            0.5,
            "config",
        )

    def test_config_for_another_provider_is_ignored(self, tmp_path: Path) -> None:
        layer = (
            '[default.pipeline.stages.tailor]\nprovider = "anthropic"\n'
            'model = "claude-sonnet-5-5"\n'
        )
        resolved = _resolve(
            tmp_path, PIPELINE_STAGES, layer, provider_override="openai"
        )
        assert _row(resolved, StageKey.TAILOR)[:2] == ("openai", "gpt-6-astra")

    def test_a_configured_temperature_still_applies(self, tmp_path: Path) -> None:
        layer = (
            '[default.pipeline.stages.tailor]\nprovider = "anthropic"\n'
            'model = "claude-sonnet-5-5"\ntemperature = 0.9\n'
        )
        resolved = _resolve(
            tmp_path, PIPELINE_STAGES, layer, provider_override="openai"
        )
        assert _row(resolved, StageKey.TAILOR)[2] == 0.9

    def test_a_provider_without_a_profile_needs_configured_models(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ConfigurationError) as caught:
            _resolve(tmp_path, provider_override="openrouter")
        message = str(caught.value)
        assert message.startswith("Cannot resolve models:")
        for stage in PIPELINE_STAGES:
            assert f"[default.pipeline.stages.{stage.value}]" in message

    def test_missing_stage_lines_follow_the_design_wording(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ConfigurationError) as caught:
            _resolve(tmp_path, provider_override="openrouter")
        assert str(caught.value).splitlines()[1] == (
            "No model for stage 'analyze' with provider 'openrouter': "
            "set model in [default.pipeline.stages.analyze] "
            "or choose a --model-profile."
        )

    def test_one_stage_per_line(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError) as caught:
            _resolve(tmp_path, provider_override="openrouter")
        assert len(str(caught.value).splitlines()) == 1 + len(PIPELINE_STAGES)

    def test_only_unresolved_stages_are_listed(self, tmp_path: Path) -> None:
        layer = (
            '[default.pipeline.stages.review]\nprovider = "openrouter"\n'
            'model = "openai/gpt-4o"\n'
        )
        with pytest.raises(ConfigurationError) as caught:
            _resolve(tmp_path, PIPELINE_STAGES, layer, provider_override="openrouter")
        assert "stage 'review'" not in str(caught.value)

    def test_user_defined_provider_resolves_entirely_from_config(
        self, tmp_path: Path
    ) -> None:
        layer = GROQ_PROVIDER + "".join(
            f'[default.pipeline.stages.{stage.value}]\nprovider = "groq"\n'
            'model = "llama-3.3-70b-versatile"\n'
            for stage in PIPELINE_STAGES
        )
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer, provider_override="groq")
        assert {(r[0], r[1], r[3]) for r in _rows(resolved).values()} == {
            ("groq", "llama-3.3-70b-versatile", "config")
        }

    def test_unknown_provider_is_a_configuration_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="Unknown LLM provider 'nope'"):
            _resolve(tmp_path, provider_override="nope")

    def test_economy_presets_pick_the_economy_variant(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, provider_override="openai", preset_name="concise")
        assert resolved.profile is not None
        assert resolved.profile.name == "openai-economy"

    def test_the_provider_kind_comes_from_the_registry(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, provider_override="google")
        kinds = {a.provider_kind for a in resolved.assignments.values()}
        assert kinds == {ProviderKind.GOOGLE}

    def test_a_model_only_config_entry_is_not_config_for_the_overridden_provider(
        self, tmp_path: Path
    ) -> None:
        layer = '[default.pipeline.stages.tailor]\nmodel = "gpt-6.1-sol"\n'
        resolved = _resolve(
            tmp_path, PIPELINE_STAGES, layer, provider_override="openai"
        )
        assert _row(resolved, StageKey.TAILOR)[:2] == ("openai", "gpt-6-astra")


class TestLegacyPresetsAndProfiles:
    """REQ-SR-6."""

    def test_budget_runs_every_stage_on_ollama(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, preset_name="budget")
        assert {(r[0], r[1]) for r in _rows(resolved).values()} == {
            ("ollama", "llama3.1:8b")
        }

    def test_budget_profile_source_is_the_preset(self, tmp_path: Path) -> None:
        assert _resolve(tmp_path, preset_name="budget").profile_source == "preset"

    def test_budget_stage_sources_come_from_the_profile(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, preset_name="budget")
        assert {r[3] for r in _rows(resolved).values()} == {"profile"}

    def test_budget_ignores_config_for_other_providers(self, tmp_path: Path) -> None:
        layer = (
            '[default.pipeline.stages.analyze]\nprovider = "openai"\n'
            'model = "gpt-6-luna"\ntemperature = 0.9\n'
        )
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer, preset_name="budget")
        assert _row(resolved, StageKey.ANALYZE)[:2] == ("ollama", "llama3.1:8b")

    def test_budget_keeps_config_for_ollama(self, tmp_path: Path) -> None:
        layer = (
            '[default.pipeline.stages.analyze]\nprovider = "ollama"\n'
            'model = "qwen3:14b"\n'
        )
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer, preset_name="budget")
        assert _row(resolved, StageKey.ANALYZE) == (
            "ollama",
            "qwen3:14b",
            0.2,
            "config",
        )

    def test_premium_equals_standard(self, tmp_path: Path) -> None:
        premium = _resolve(tmp_path, preset_name="premium")
        assert _rows(premium) == STANDARD_ROWS

    def test_default_equals_standard(self, tmp_path: Path) -> None:
        default = _resolve(tmp_path, preset_name="default")
        assert _rows(default) == STANDARD_ROWS

    def test_an_unknown_preset_behaves_like_default(self, tmp_path: Path) -> None:
        assert _rows(_resolve(tmp_path, preset_name="nonexistent")) == STANDARD_ROWS

    def test_the_cli_mapping_of_profile_budget_still_yields_ollama(
        self, tmp_path: Path
    ) -> None:
        resolved = _resolve(tmp_path, preset_name="concise", provider_override="ollama")
        assert {(r[0], r[1]) for r in _rows(resolved).values()} == {
            ("ollama", "llama3.1:8b")
        }


class TestKnowledgeBaseOverrides:
    """REQ-SR-7."""

    def test_model_and_provider_override(self, tmp_path: Path) -> None:
        resolved = _resolve(
            tmp_path,
            (StageKey.KB,),
            model_override="gpt-6.1-sol",
            provider_override="openai",
        )
        assert _row(resolved, StageKey.KB) == ("openai", "gpt-6.1-sol", 0.3, "cli")

    def test_provider_override_alone_uses_the_profile_model(
        self, tmp_path: Path
    ) -> None:
        resolved = _resolve(tmp_path, (StageKey.KB,), provider_override="google")
        assert _row(resolved, StageKey.KB)[:2] == ("google", "gemini-3.8-flash")

    def test_model_override_alone_keeps_the_configured_provider(
        self, tmp_path: Path
    ) -> None:
        layer = '[default.kb]\nprovider = "openai"\n'
        resolved = _resolve(
            tmp_path, (StageKey.KB,), layer, model_override="gpt-6-luna"
        )
        assert _row(resolved, StageKey.KB)[:2] == ("openai", "gpt-6-luna")

    def test_model_override_alone_defaults_to_the_profile_provider(
        self, tmp_path: Path
    ) -> None:
        resolved = _resolve(tmp_path, (StageKey.KB,), model_override="claude-haiku-5-5")
        assert _row(resolved, StageKey.KB) == (
            "anthropic",
            "claude-haiku-5-5",
            0.3,
            "cli",
        )

    def test_model_override_does_not_touch_other_stages(self, tmp_path: Path) -> None:
        resolved = _resolve(
            tmp_path,
            (StageKey.KB, StageKey.VALIDATE),
            model_override="claude-haiku-5-5",
        )
        assert _row(resolved, StageKey.VALIDATE)[3] == "profile"

    def test_configured_kb_model_is_used_without_overrides(
        self, tmp_path: Path
    ) -> None:
        layer = '[default.kb]\nmodel = "claude-opus-5-5"\n'
        resolved = _resolve(tmp_path, (StageKey.KB,), layer)
        assert _row(resolved, StageKey.KB) == (
            "anthropic",
            "claude-opus-5-5",
            0.3,
            "config",
        )


class TestStubProvider:
    def test_stub_needs_no_recommended_model(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, provider_override="stub")
        assert {(r[0], r[1]) for r in _rows(resolved).values()} == {
            ("stub", "stub-model")
        }

    def test_stub_stages_report_the_stub_kind(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path, (StageKey.KB,), provider_override="stub")
        assert resolved.assignments[StageKey.KB].provider_kind is ProviderKind.STUB

    def test_a_configured_model_still_wins_for_the_stub(self, tmp_path: Path) -> None:
        layer = '[default.kb]\nprovider = "stub"\nmodel = "custom-kb-model"\n'
        resolved = _resolve(tmp_path, (StageKey.KB,), layer, provider_override="stub")
        assert _row(resolved, StageKey.KB)[:2] == ("stub", "custom-kb-model")

    def test_a_stage_configured_for_the_stub_resolves(self, tmp_path: Path) -> None:
        layer = '[default.pipeline.stages.analyze]\nprovider = "stub"\n'
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer)
        assert _row(resolved, StageKey.ANALYZE)[:2] == ("stub", "stub-model")


class TestInvalidSettings:
    def test_temperature_must_be_a_number(self, tmp_path: Path) -> None:
        layer = '[default.pipeline.stages.tailor]\ntemperature = "hot"\n'
        with pytest.raises(
            ConfigurationError, match=r"temperature.*pipeline\.stages\.tailor"
        ):
            _resolve(tmp_path, PIPELINE_STAGES, layer)

    @pytest.mark.parametrize("value", ["-0.1", "2.5"])
    def test_temperature_must_be_within_the_sampling_range(
        self, tmp_path: Path, value: str
    ) -> None:
        layer = f"[default.pipeline.stages.tailor]\ntemperature = {value}\n"
        with pytest.raises(ConfigurationError, match="between 0 and 2"):
            _resolve(tmp_path, PIPELINE_STAGES, layer)

    @pytest.mark.parametrize("value", ["0", "2", "1"])
    def test_integer_temperatures_are_accepted(
        self, tmp_path: Path, value: str
    ) -> None:
        layer = f"[default.pipeline.stages.tailor]\ntemperature = {value}\n"
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer)
        assert _row(resolved, StageKey.TAILOR)[2] == float(value)

    def test_model_must_be_a_string(self, tmp_path: Path) -> None:
        layer = "[default.pipeline.stages.tailor]\nmodel = 5\n"
        with pytest.raises(ConfigurationError, match=r"model.*must be a string"):
            _resolve(tmp_path, PIPELINE_STAGES, layer)

    def test_a_stage_section_must_be_a_table(self, tmp_path: Path) -> None:
        layer = '[default.pipeline.stages]\ntailor = "gpt-6"\n'
        with pytest.raises(ConfigurationError, match="must be a table"):
            _resolve(tmp_path, PIPELINE_STAGES, layer)

    def test_model_profile_must_be_a_string(self, tmp_path: Path) -> None:
        layer = "[default.pipeline]\nmodel_profile = 3\n"
        with pytest.raises(ConfigurationError, match=r"model_profile.*string"):
            _resolve(tmp_path, PIPELINE_STAGES, layer)

    def test_an_empty_model_counts_as_unset(self, tmp_path: Path) -> None:
        layer = '[default.pipeline.stages.tailor]\nmodel = ""\n'
        resolved = _resolve(tmp_path, PIPELINE_STAGES, layer)
        assert _row(resolved, StageKey.TAILOR)[3] == "profile"


class TestResolutionLogging:
    def test_each_assignment_is_logged_at_info(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO, logger="mkcv.adapters.llm.stage_resolver")
        _resolve(tmp_path, (StageKey.TAILOR,))
        assert (
            "Stage tailor: anthropic/claude-opus-5-5 (source=profile, temperature=0.50)"
            in caplog.text
        )


class TestResolutionRequest:
    def test_defaults(self) -> None:
        request = ResolutionRequest()
        assert (
            request.preset_name,
            request.model_profile,
            request.provider_override,
            request.model_override,
        ) == ("default", None, None, None)

    def test_requests_are_frozen(self) -> None:
        with pytest.raises(ValidationError):
            ResolutionRequest().preset_name = "x"  # type: ignore[misc]


class TestResolvedStages:
    def test_pipeline_stage_configs_number_the_five_stages(
        self, tmp_path: Path
    ) -> None:
        configs = _resolve(tmp_path, preset_name="standard").pipeline_stage_configs()
        assert configs == {
            1: StageConfig(
                provider="anthropic", model="claude-haiku-5-5", temperature=0.2
            ),
            2: StageConfig(
                provider="anthropic", model="claude-opus-5-5", temperature=0.3
            ),
            3: StageConfig(
                provider="anthropic", model="claude-opus-5-5", temperature=0.5
            ),
            4: StageConfig(
                provider="anthropic", model="claude-sonnet-5-5", temperature=0.1
            ),
            5: StageConfig(
                provider="anthropic", model="claude-opus-5-5", temperature=0.3
            ),
        }

    def test_pipeline_stage_configs_skip_other_stages(self, tmp_path: Path) -> None:
        resolved = _resolve(
            tmp_path, (StageKey.TAILOR, StageKey.KB, StageKey.COVER_LETTER_REVIEW)
        )
        assert list(resolved.pipeline_stage_configs()) == [3]

    def test_results_are_frozen(self, tmp_path: Path) -> None:
        resolved = _resolve(tmp_path)
        with pytest.raises(ValidationError):
            resolved.preset_name = "x"  # type: ignore[misc]


class TestRegistryIntegration:
    def test_resolver_uses_the_registry_it_was_given(self, tmp_path: Path) -> None:
        layer = GROQ_PROVIDER + '[default.kb]\nprovider = "groq"\nmodel = "m"\n'
        resolved = _resolve(tmp_path, (StageKey.KB,), layer)
        assignment = resolved.assignments[StageKey.KB]
        assert (assignment.provider, assignment.provider_kind) == (
            "groq",
            ProviderKind.OPENAI_COMPATIBLE,
        )
