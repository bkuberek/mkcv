"""Tests for Preset model, built-in presets, and backward compatibility."""

from mkcv.core.models.profile_preset import (
    BUILT_IN_PRESETS,
    VALID_PRESET_NAMES,
    VALID_PROFILES,
    ContentDensity,
    Preset,
    resolve_preset,
)
from mkcv.core.models.stage_config import StageConfig


class TestContentDensity:
    """Tests for the ContentDensity enum."""

    def test_concise_value(self) -> None:
        assert ContentDensity.CONCISE.value == "concise"

    def test_standard_value(self) -> None:
        assert ContentDensity.STANDARD.value == "standard"

    def test_comprehensive_value(self) -> None:
        assert ContentDensity.COMPREHENSIVE.value == "comprehensive"

    def test_is_string_enum(self) -> None:
        assert isinstance(ContentDensity.CONCISE, str)


class TestPresetModel:
    """Tests for the Preset Pydantic model."""

    def test_creates_valid_preset(self) -> None:
        preset = Preset(
            name="test",
            description="A test preset",
            density=ContentDensity.STANDARD,
            page_budget="1-2",
            max_roles=4,
            max_bullets_primary=5,
            max_bullets_secondary=3,
            include_earlier_experience=True,
            stage_configs={
                1: StageConfig(provider="stub", model="m", temperature=0.2),
            },
        )
        assert preset.name == "test"
        assert preset.density == ContentDensity.STANDARD

    def test_preset_serializes_to_dict(self) -> None:
        preset = Preset(
            name="test",
            description="desc",
            density=ContentDensity.CONCISE,
            page_budget="1",
            max_roles=3,
            max_bullets_primary=4,
            max_bullets_secondary=2,
            include_earlier_experience=False,
            stage_configs={},
        )
        data = preset.model_dump()
        assert data["density"] == "concise"
        assert data["max_roles"] == 3


class TestBuiltInPresets:
    """Tests for the BUILT_IN_PRESETS dictionary."""

    def test_concise_preset_exists(self) -> None:
        assert "concise" in BUILT_IN_PRESETS

    def test_standard_preset_exists(self) -> None:
        assert "standard" in BUILT_IN_PRESETS

    def test_comprehensive_preset_exists(self) -> None:
        assert "comprehensive" in BUILT_IN_PRESETS

    def test_concise_density(self) -> None:
        assert BUILT_IN_PRESETS["concise"].density == ContentDensity.CONCISE

    def test_standard_density(self) -> None:
        assert BUILT_IN_PRESETS["standard"].density == ContentDensity.STANDARD

    def test_comprehensive_density(self) -> None:
        preset = BUILT_IN_PRESETS["comprehensive"]
        assert preset.density == ContentDensity.COMPREHENSIVE

    def test_concise_page_budget(self) -> None:
        assert BUILT_IN_PRESETS["concise"].page_budget == "1"

    def test_standard_page_budget(self) -> None:
        assert BUILT_IN_PRESETS["standard"].page_budget == "1-2"

    def test_comprehensive_page_budget(self) -> None:
        assert BUILT_IN_PRESETS["comprehensive"].page_budget == "2+"

    def test_concise_max_roles(self) -> None:
        assert BUILT_IN_PRESETS["concise"].max_roles == 3

    def test_standard_max_roles(self) -> None:
        assert BUILT_IN_PRESETS["standard"].max_roles == 4

    def test_comprehensive_max_roles(self) -> None:
        assert BUILT_IN_PRESETS["comprehensive"].max_roles == 6

    def test_concise_no_earlier_experience(self) -> None:
        assert BUILT_IN_PRESETS["concise"].include_earlier_experience is False

    def test_standard_includes_earlier_experience(self) -> None:
        assert BUILT_IN_PRESETS["standard"].include_earlier_experience is True

    def test_comprehensive_includes_earlier_experience(self) -> None:
        assert BUILT_IN_PRESETS["comprehensive"].include_earlier_experience is True

    def test_concise_uses_haiku(self) -> None:
        preset = BUILT_IN_PRESETS["concise"]
        for sc in preset.stage_configs.values():
            assert sc.provider == "anthropic"
            assert "haiku" in sc.model

    def test_standard_uses_smart_mix(self) -> None:
        preset = BUILT_IN_PRESETS["standard"]
        for sc in preset.stage_configs.values():
            assert sc.provider == "anthropic"
        # Smart mix: stages 1,4 = Haiku; stages 2,3,5 = Opus
        assert "haiku" in preset.stage_configs[1].model
        assert "opus" in preset.stage_configs[2].model
        assert "opus" in preset.stage_configs[3].model
        assert "haiku" in preset.stage_configs[4].model
        assert "opus" in preset.stage_configs[5].model

    def test_comprehensive_uses_smart_mix(self) -> None:
        preset = BUILT_IN_PRESETS["comprehensive"]
        for sc in preset.stage_configs.values():
            assert sc.provider == "anthropic"
        # Smart mix: stages 1,4 = Haiku; stages 2,3,5 = Opus
        assert "haiku" in preset.stage_configs[1].model
        assert "opus" in preset.stage_configs[2].model
        assert "opus" in preset.stage_configs[3].model
        assert "haiku" in preset.stage_configs[4].model
        assert "opus" in preset.stage_configs[5].model

    def test_all_presets_have_five_stages(self) -> None:
        for name, preset in BUILT_IN_PRESETS.items():
            assert set(preset.stage_configs.keys()) == {1, 2, 3, 4, 5}, (
                f"Preset '{name}' missing stages"
            )

    def test_concise_bullet_counts(self) -> None:
        preset = BUILT_IN_PRESETS["concise"]
        assert preset.max_bullets_primary == 4
        assert preset.max_bullets_secondary == 2

    def test_standard_bullet_counts(self) -> None:
        preset = BUILT_IN_PRESETS["standard"]
        assert preset.max_bullets_primary == 5
        assert preset.max_bullets_secondary == 3

    def test_comprehensive_bullet_counts(self) -> None:
        preset = BUILT_IN_PRESETS["comprehensive"]
        assert preset.max_bullets_primary == 7
        assert preset.max_bullets_secondary == 5


class TestValidPresetNames:
    """Tests for VALID_PRESET_NAMES frozenset."""

    def test_contains_concise(self) -> None:
        assert "concise" in VALID_PRESET_NAMES

    def test_contains_standard(self) -> None:
        assert "standard" in VALID_PRESET_NAMES

    def test_contains_comprehensive(self) -> None:
        assert "comprehensive" in VALID_PRESET_NAMES

    def test_matches_built_in_keys(self) -> None:
        assert frozenset(BUILT_IN_PRESETS.keys()) == VALID_PRESET_NAMES


class TestBackwardCompatibility:
    """Tests for legacy profile name mapping."""

    def test_valid_profiles_includes_budget(self) -> None:
        assert "budget" in VALID_PROFILES

    def test_valid_profiles_includes_premium(self) -> None:
        assert "premium" in VALID_PROFILES

    def test_valid_profiles_includes_default(self) -> None:
        assert "default" in VALID_PROFILES

    def test_valid_profiles_includes_new_presets(self) -> None:
        for name in VALID_PRESET_NAMES:
            assert name in VALID_PROFILES

    def test_resolve_budget_returns_ollama_preset(self) -> None:
        preset = resolve_preset("budget")
        assert preset is not None
        assert preset.name == "budget"
        for sc in preset.stage_configs.values():
            assert sc.provider == "ollama"

    def test_resolve_budget_uses_concise_density(self) -> None:
        preset = resolve_preset("budget")
        assert preset is not None
        assert preset.density == ContentDensity.CONCISE

    def test_resolve_premium_returns_standard_preset(self) -> None:
        preset = resolve_preset("premium")
        assert preset is not None
        assert preset.density == ContentDensity.STANDARD

    def test_resolve_premium_uses_anthropic(self) -> None:
        preset = resolve_preset("premium")
        assert preset is not None
        for sc in preset.stage_configs.values():
            assert sc.provider == "anthropic"


class TestResolvePreset:
    """Tests for the resolve_preset function."""

    def test_resolves_concise(self) -> None:
        preset = resolve_preset("concise")
        assert preset is not None
        assert preset.name == "concise"

    def test_resolves_standard(self) -> None:
        preset = resolve_preset("standard")
        assert preset is not None
        assert preset.name == "standard"

    def test_resolves_comprehensive(self) -> None:
        preset = resolve_preset("comprehensive")
        assert preset is not None
        assert preset.name == "comprehensive"

    def test_returns_none_for_default(self) -> None:
        assert resolve_preset("default") is None

    def test_returns_none_for_unknown(self) -> None:
        assert resolve_preset("nonexistent") is None

    def test_builtin_takes_precedence_over_legacy(self) -> None:
        """If a name exists in both dicts, built-in wins."""
        preset = resolve_preset("concise")
        assert preset is not None
        assert preset.name == "concise"
