"""Tests for the built-in model profiles (REQ-MP-1, design section 6.2)."""

import subprocess
import sys

import pytest
from pydantic import ValidationError

from mkcv.core.catalog.builtin_model_profiles import (
    BUILTIN_MODEL_PROFILES,
    get_profile,
    profile_for_provider,
    profile_stage_model,
)
from mkcv.core.catalog.stage_requirements import STAGE_REQUIREMENTS
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.model_profile import ModelProfile
from mkcv.core.models.stage_key import PIPELINE_STAGES, StageKey

_ALL_NAMES = [
    "anthropic",
    "anthropic-economy",
    "openai",
    "openai-economy",
    "google",
    "google-economy",
    "local",
]
_BASE_NAMES = ["anthropic", "openai", "google", "local"]
_ECONOMY_NAMES = ["anthropic-economy", "openai-economy", "google-economy"]

_S = StageKey
# Column order follows the design table: analyze, select, tailor, structure,
# review, cover_letter.generate, cover_letter.review, kb, validate.
_STAGE_ORDER = (
    _S.ANALYZE,
    _S.SELECT,
    _S.TAILOR,
    _S.STRUCTURE,
    _S.REVIEW,
    _S.COVER_LETTER_GENERATE,
    _S.COVER_LETTER_REVIEW,
    _S.KB,
    _S.VALIDATE,
)
_BASE_MODELS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "anthropic": (
        "anthropic",
        "Recommended Claude mix: Haiku for extraction, Opus for decisions and "
        "writing, Sonnet for YAML.",
        (
            "claude-haiku-5-5",
            "claude-opus-5-5",
            "claude-opus-5-5",
            "claude-sonnet-5-5",
            "claude-opus-5-5",
            "claude-opus-5-5",
            "claude-haiku-5-5",
            "claude-sonnet-5-5",
            "claude-sonnet-5-5",
        ),
    ),
    "openai": (
        "openai",
        "Recommended OpenAI mix: Luna for extraction, Astra for writing, Sol "
        "for decisions, Terra for YAML.",
        (
            "gpt-6-luna",
            "gpt-6.1-sol",
            "gpt-6-astra",
            "gpt-6.1-terra",
            "gpt-6.1-sol",
            "gpt-6-astra",
            "gpt-6-luna",
            "gpt-6.1-sol",
            "gpt-6.1-terra",
        ),
    ),
    "google": (
        "google",
        "Recommended Gemini mix: Flash-Lite for extraction, Argon for decisions "
        "and writing, Flash for YAML.",
        (
            "gemini-3.5-flash-lite",
            "gemini-4-argon",
            "gemini-4-argon",
            "gemini-3.8-flash",
            "gemini-4-argon",
            "gemini-4-argon",
            "gemini-3.5-flash-lite",
            "gemini-3.8-flash",
            "gemini-3.8-flash",
        ),
    ),
    "local": (
        "ollama",
        "Local Ollama model for every stage (free, offline, lowest quality).",
        ("llama3.1:8b",) * 9,
    ),
}
_ECONOMY_MODELS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "anthropic-economy": (
        "anthropic",
        "anthropic",
        "Claude Haiku for every resume stage (fast, low cost).",
        ("claude-haiku-5-5",) * 5,
    ),
    "openai-economy": (
        "openai",
        "openai",
        "Low-cost OpenAI mix: Luna and Terra.",
        (
            "gpt-6-luna",
            "gpt-6.1-terra",
            "gpt-6.1-terra",
            "gpt-6-luna",
            "gpt-6.1-terra",
        ),
    ),
    "google-economy": (
        "google",
        "google",
        "Low-cost Gemini mix: Flash-Lite and Flash.",
        (
            "gemini-3.5-flash-lite",
            "gemini-3.8-flash",
            "gemini-3.8-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.8-flash",
        ),
    ),
}


def _profile(name: str) -> ModelProfile:
    profile = get_profile(name)
    assert profile is not None
    return profile


class TestProfileSet:
    def test_contains_exactly_the_seven_profiles(self) -> None:
        assert set(BUILTIN_MODEL_PROFILES) == set(_ALL_NAMES)

    def test_every_key_is_the_profile_name(self) -> None:
        for name, profile in BUILTIN_MODEL_PROFILES.items():
            assert profile.name == name

    def test_every_profile_is_provisional(self) -> None:
        assert {p.evidence for p in BUILTIN_MODEL_PROFILES.values()} == {"provisional"}

    def test_no_profile_cites_an_eval_run(self) -> None:
        assert {p.eval_run for p in BUILTIN_MODEL_PROFILES.values()} == {None}

    def test_no_profile_is_called_budget(self) -> None:
        assert "budget" not in BUILTIN_MODEL_PROFILES


@pytest.mark.parametrize("name", _BASE_NAMES)
class TestBaseProfiles:
    def test_provider(self, name: str) -> None:
        assert _profile(name).provider == _BASE_MODELS[name][0]

    def test_is_not_an_economy_profile(self, name: str) -> None:
        profile = _profile(name)
        assert (profile.economy, profile.extends) == (False, None)

    def test_description(self, name: str) -> None:
        assert _profile(name).description == _BASE_MODELS[name][1]

    def test_stage_models(self, name: str) -> None:
        profile = _profile(name)
        expected = dict(zip(_STAGE_ORDER, _BASE_MODELS[name][2], strict=True))
        assert profile.stages == expected

    def test_names_a_model_for_all_nine_stages(self, name: str) -> None:
        assert set(_profile(name).stages) == set(StageKey)


@pytest.mark.parametrize("name", _ECONOMY_NAMES)
class TestEconomyProfiles:
    def test_provider(self, name: str) -> None:
        assert _profile(name).provider == _ECONOMY_MODELS[name][0]

    def test_extends_the_base_profile_of_the_same_provider(self, name: str) -> None:
        profile = _profile(name)
        assert profile.extends == _ECONOMY_MODELS[name][1]
        assert _profile(profile.extends).provider == profile.provider

    def test_is_an_economy_profile(self, name: str) -> None:
        assert _profile(name).economy is True

    def test_description(self, name: str) -> None:
        assert _profile(name).description == _ECONOMY_MODELS[name][2]

    def test_lists_only_the_five_pipeline_stages(self, name: str) -> None:
        assert tuple(_profile(name).stages) == PIPELINE_STAGES

    def test_stage_models(self, name: str) -> None:
        expected = dict(zip(PIPELINE_STAGES, _ECONOMY_MODELS[name][3], strict=True))
        assert _profile(name).stages == expected


class TestExtendsChains:
    def test_extends_targets_exist_and_are_base_profiles(self) -> None:
        for profile in BUILTIN_MODEL_PROFILES.values():
            if profile.extends is not None:
                base = BUILTIN_MODEL_PROFILES[profile.extends]
                assert base.extends is None

    def test_only_economy_profiles_extend(self) -> None:
        extending = {p.name for p in BUILTIN_MODEL_PROFILES.values() if p.extends}
        assert extending == set(_ECONOMY_NAMES)

    def test_every_provider_has_at_most_one_profile_per_economy_flag(self) -> None:
        keys = [(p.provider, p.economy) for p in BUILTIN_MODEL_PROFILES.values()]
        assert len(keys) == len(set(keys))


class TestCatalogConsistency:
    """REQ-MP-1: every profile model is described by the catalog."""

    @staticmethod
    def _assignments() -> list[tuple[str, StageKey, str, str]]:
        return [
            (name, stage, profile.provider, model)
            for name, profile in BUILTIN_MODEL_PROFILES.items()
            for stage, model in profile.stages.items()
        ]

    def test_every_profile_model_has_an_exact_catalog_entry(self) -> None:
        catalog = ModelCatalog.builtin()
        exact = {
            (entry.provider, entry.match)
            for entry in catalog.entries
            if entry.match_type == "exact"
        }
        missing = [
            f"{name}/{stage}: {provider}/{model}"
            for name, stage, provider, model in self._assignments()
            if provider != "ollama" and (provider, model) not in exact
        ]
        assert missing == []

    def test_the_local_model_matches_the_ollama_prefix_entry(self) -> None:
        catalog = ModelCatalog.builtin()
        assert catalog.lookup("ollama", "llama3.1:8b") is not None
        assert any(
            entry.provider == "ollama"
            and entry.match == "llama3.1"
            and entry.match_type == "prefix"
            for entry in catalog.entries
        )

    def test_every_cloud_profile_model_has_prices_for_cost_estimates(self) -> None:
        catalog = ModelCatalog.builtin()
        unpriced = [
            f"{name}/{stage}: {provider}/{model}"
            for name, stage, provider, model in self._assignments()
            if provider != "ollama"
            and catalog.price_for(model, provider=provider) is None
        ]
        assert unpriced == []

    def test_no_profile_model_is_deprecated(self) -> None:
        catalog = ModelCatalog.builtin()
        deprecated = [
            f"{name}/{stage}: {provider}/{model}"
            for name, stage, provider, model in self._assignments()
            if (entry := catalog.lookup(provider, model)) is not None
            and entry.deprecated
        ]
        assert deprecated == []

    @pytest.mark.parametrize("name", ["anthropic", "openai", "google"])
    def test_recommended_models_meet_each_stages_minimum_tier(self, name: str) -> None:
        catalog = ModelCatalog.builtin()
        profile = _profile(name)
        below = []
        for stage, model in profile.stages.items():
            entry = catalog.lookup(profile.provider, model)
            assert entry is not None and entry.tier is not None
            if entry.tier.rank() < STAGE_REQUIREMENTS[stage].min_tier.rank():
                below.append(f"{stage}: {model} is {entry.tier}")
        assert below == []


class TestGetProfile:
    @pytest.mark.parametrize("name", _ALL_NAMES)
    def test_returns_the_named_profile(self, name: str) -> None:
        assert get_profile(name) is BUILTIN_MODEL_PROFILES[name]

    @pytest.mark.parametrize("name", ["nope", "budget", "Anthropic", ""])
    def test_returns_none_for_other_names(self, name: str) -> None:
        assert get_profile(name) is None


class TestProfileStageModel:
    def test_own_stage_model_is_returned(self) -> None:
        assert profile_stage_model(_profile("openai"), StageKey.TAILOR) == (
            "gpt-6-astra"
        )

    def test_economy_profile_uses_its_own_pipeline_models(self) -> None:
        assert profile_stage_model(_profile("openai-economy"), StageKey.TAILOR) == (
            "gpt-6.1-terra"
        )

    def test_economy_profile_inherits_cover_letter_models(self) -> None:
        profile = _profile("openai-economy")
        assert profile_stage_model(profile, StageKey.COVER_LETTER_GENERATE) == (
            "gpt-6-astra"
        )

    @pytest.mark.parametrize("stage", [StageKey.KB, StageKey.VALIDATE])
    def test_economy_profile_inherits_kb_and_validate_models(
        self, stage: StageKey
    ) -> None:
        economy = profile_stage_model(_profile("anthropic-economy"), stage)
        assert economy == profile_stage_model(_profile("anthropic"), stage)

    def test_economy_profile_does_not_inherit_what_it_overrides(self) -> None:
        profile = _profile("anthropic-economy")
        assert profile_stage_model(profile, StageKey.REVIEW) == "claude-haiku-5-5"

    def test_missing_stage_without_a_base_profile_gives_none(self) -> None:
        profile = ModelProfile(
            name="partial",
            description="d",
            provider="openai",
            stages={StageKey.ANALYZE: "gpt-6-luna"},
        )
        assert profile_stage_model(profile, StageKey.TAILOR) is None

    def test_unknown_base_profile_gives_none(self) -> None:
        profile = ModelProfile(
            name="orphan",
            description="d",
            provider="openai",
            extends="does-not-exist",
            stages={},
        )
        assert profile_stage_model(profile, StageKey.TAILOR) is None

    @pytest.mark.parametrize("name", _ALL_NAMES)
    def test_every_builtin_profile_resolves_all_nine_stages(self, name: str) -> None:
        profile = _profile(name)
        assert all(profile_stage_model(profile, stage) for stage in StageKey)


class TestProfileForProvider:
    @pytest.mark.parametrize("provider", ["anthropic", "openai", "google"])
    def test_non_economy_lookup(self, provider: str) -> None:
        profile = profile_for_provider(provider, economy=False)
        assert profile is not None and profile.name == provider

    @pytest.mark.parametrize("provider", ["anthropic", "openai", "google"])
    def test_economy_lookup(self, provider: str) -> None:
        profile = profile_for_provider(provider, economy=True)
        assert profile is not None and profile.name == f"{provider}-economy"

    def test_ollama_has_only_the_local_profile(self) -> None:
        profile = profile_for_provider("ollama", economy=False)
        assert profile is not None and profile.name == "local"

    def test_economy_request_falls_back_to_the_non_economy_profile(self) -> None:
        profile = profile_for_provider("ollama", economy=True)
        assert profile is not None and profile.name == "local"

    @pytest.mark.parametrize("economy", [False, True])
    def test_providers_without_a_profile_give_none(self, economy: bool) -> None:
        assert profile_for_provider("openrouter", economy=economy) is None

    def test_user_defined_providers_give_none(self) -> None:
        assert profile_for_provider("groq", economy=False) is None


class TestModelProfileModel:
    def test_defaults(self) -> None:
        profile = ModelProfile(name="p", description="d", provider="openai", stages={})
        assert (
            profile.economy,
            profile.extends,
            profile.evidence,
            profile.eval_run,
        ) == (False, None, "provisional", None)

    def test_profiles_are_frozen(self) -> None:
        with pytest.raises(ValidationError):
            _profile("openai").provider = "google"  # type: ignore[misc]

    def test_evidence_accepts_only_known_values(self) -> None:
        with pytest.raises(ValidationError):
            ModelProfile(
                name="p",
                description="d",
                provider="openai",
                evidence="guess",  # type: ignore[arg-type]
                stages={},
            )

    def test_eval_backed_profiles_can_cite_their_run(self) -> None:
        profile = ModelProfile(
            name="p",
            description="d",
            provider="openai",
            evidence="eval",
            eval_run="2026-11-10T12-00-00",
            stages={},
        )
        assert (profile.evidence, profile.eval_run) == ("eval", "2026-11-10T12-00-00")

    def test_stage_keys_are_validated(self) -> None:
        with pytest.raises(ValidationError):
            ModelProfile.model_validate(
                {
                    "name": "p",
                    "description": "d",
                    "provider": "openai",
                    "stages": {"translate": "m"},
                }
            )

    def test_stage_keys_accept_their_string_values(self) -> None:
        profile = ModelProfile.model_validate(
            {
                "name": "p",
                "description": "d",
                "provider": "openai",
                "stages": {"cover_letter.review": "m"},
            }
        )
        assert profile.stages == {StageKey.COVER_LETTER_REVIEW: "m"}


class TestImports:
    @pytest.mark.parametrize(
        "module",
        [
            "mkcv.core.catalog.builtin_model_profiles",
            "mkcv.core.catalog.stage_requirements",
        ],
    )
    def test_module_imports_first_in_a_fresh_interpreter(self, module: str) -> None:
        result = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    def test_core_modules_do_not_import_adapters_or_config(self) -> None:
        code = (
            "import sys; "
            "import mkcv.core.catalog.builtin_model_profiles, "
            "mkcv.core.catalog.stage_requirements; "
            "bad = [m for m in sys.modules "
            "if m.startswith(('mkcv.adapters', 'mkcv.config', 'mkcv.cli'))]; "
            "assert not bad, bad"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
