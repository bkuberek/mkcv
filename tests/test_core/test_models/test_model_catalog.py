"""Tests for the model capability catalog and its value objects."""

from typing import Any

import pytest
from pydantic import ValidationError

from mkcv.core.models.capability_overlay import CapabilityOverlay
from mkcv.core.models.model_capability import ModelCapability
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.model_tier import ModelTier
from mkcv.core.models.resolved_model import ResolvedModel
from mkcv.core.models.structured_output_mode import StructuredOutputMode
from mkcv.core.models.token_param import TokenParam

# Kind defaults from design section 5.2, rebuilt here so catalog tests do not
# depend on the adapter layer.
OPENAI_DEFAULTS = CapabilityOverlay(
    structured_output=StructuredOutputMode.JSON_SCHEMA,
    allow_structured_fallback=False,
    accepts_sampling_params=False,
    token_param=TokenParam.MAX_COMPLETION_TOKENS,
    min_output_tokens=16000,
)
COMPATIBLE_DEFAULTS = CapabilityOverlay(
    structured_output=StructuredOutputMode.JSON_SCHEMA,
    allow_structured_fallback=True,
    accepts_sampling_params=True,
    token_param=TokenParam.MAX_TOKENS,
    min_output_tokens=0,
)


def _cap(
    provider: str,
    match: str,
    *,
    match_type: str = "exact",
    **fields: Any,
) -> ModelCapability:
    return ModelCapability(
        provider=provider,
        match=match,
        match_type=match_type,  # type: ignore[arg-type]
        **fields,
    )


def _resolved(**overrides: Any) -> ResolvedModel:
    values: dict[str, Any] = {
        "provider": "anthropic",
        "model": "claude-test-1",
        "known": True,
        "structured_output": StructuredOutputMode.JSON_SCHEMA,
        "allow_structured_fallback": False,
        "accepts_sampling_params": False,
        "token_param": TokenParam.MAX_TOKENS,
        "min_output_tokens": 0,
        "max_output_tokens": None,
        "context_window": None,
        "input_price_per_mtok": None,
        "output_price_per_mtok": None,
        "tier": None,
        "deprecated": False,
        "notes": None,
    }
    values.update(overrides)
    return ResolvedModel(**values)


class TestModelTier:
    def test_rank_orders_tiers_from_minimal_to_frontier(self) -> None:
        ranks = [tier.rank() for tier in ModelTier]
        assert ranks == [0, 1, 2, 3]

    def test_rank_follows_declared_quality_order(self) -> None:
        assert ModelTier.MINIMAL.rank() < ModelTier.EFFICIENT.rank()
        assert ModelTier.STRONG.rank() < ModelTier.FRONTIER.rank()


class TestCapabilityOverlay:
    def test_every_field_defaults_to_none(self) -> None:
        overlay = CapabilityOverlay()
        assert all(value is None for value in overlay.model_dump().values())

    def test_overlay_replaces_fields_set_on_other(self) -> None:
        base = CapabilityOverlay(tier=ModelTier.MINIMAL, notes="base")
        result = base.overlay(CapabilityOverlay(tier=ModelTier.STRONG))
        assert result.tier is ModelTier.STRONG

    def test_overlay_keeps_fields_other_leaves_unset(self) -> None:
        base = CapabilityOverlay(tier=ModelTier.MINIMAL, notes="base")
        result = base.overlay(CapabilityOverlay(tier=ModelTier.STRONG))
        assert result.notes == "base"

    def test_overlay_does_not_mutate_either_operand(self) -> None:
        base = CapabilityOverlay(tier=ModelTier.MINIMAL)
        other = CapabilityOverlay(tier=ModelTier.STRONG)
        base.overlay(other)
        assert base.tier is ModelTier.MINIMAL
        assert other.tier is ModelTier.STRONG

    def test_overlay_returns_plain_overlay_when_self_is_a_catalog_entry(self) -> None:
        entry = _cap("openai", "gpt-x", tier=ModelTier.EFFICIENT)
        result = entry.overlay(CapabilityOverlay(notes="n"))
        assert type(result) is CapabilityOverlay

    def test_overlay_is_frozen(self) -> None:
        overlay = CapabilityOverlay(tier=ModelTier.STRONG)
        with pytest.raises(ValidationError):
            overlay.tier = ModelTier.MINIMAL  # type: ignore[misc]

    def test_unknown_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CapabilityOverlay(colour="red")  # type: ignore[call-arg]

    @pytest.mark.parametrize(
        "field",
        [
            "min_output_tokens",
            "input_price_per_mtok",
            "output_price_per_mtok",
        ],
    )
    def test_negative_numbers_are_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError):
            CapabilityOverlay(**{field: -1})

    @pytest.mark.parametrize("field", ["max_output_tokens", "context_window"])
    def test_zero_limits_are_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError):
            CapabilityOverlay(**{field: 0})

    def test_invalid_tier_string_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CapabilityOverlay(tier="great")  # type: ignore[arg-type]

    def test_tier_string_from_config_is_coerced(self) -> None:
        overlay = CapabilityOverlay(tier="efficient")  # type: ignore[arg-type]
        assert overlay.tier is ModelTier.EFFICIENT


class TestModelCapability:
    def test_exact_entry_matches_only_the_identical_model(self) -> None:
        entry = _cap("openai", "gpt-4o")
        assert entry.matches("gpt-4o")
        assert not entry.matches("gpt-4o-mini")

    def test_prefix_entry_matches_models_that_start_with_it(self) -> None:
        entry = _cap("openai", "gpt-4o", match_type="prefix")
        assert entry.matches("gpt-4o-mini")

    def test_prefix_entry_rejects_other_models(self) -> None:
        entry = _cap("openai", "gpt-4o", match_type="prefix")
        assert not entry.matches("gpt-4.1")

    def test_key_combines_provider_match_and_type(self) -> None:
        entry = _cap("openai", "gpt-4o", match_type="prefix")
        assert entry.key == ("openai", "gpt-4o", "prefix")

    def test_match_type_defaults_to_exact(self) -> None:
        assert ModelCapability(provider="openai", match="m").match_type == "exact"

    def test_empty_provider_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelCapability(provider="", match="m")

    def test_empty_match_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelCapability(provider="openai", match="")

    def test_invalid_match_type_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelCapability(
                provider="openai",
                match="m",
                match_type="regex",  # type: ignore[arg-type]
            )


class TestResolvedModelOutputLimit:
    def test_floor_raises_a_small_request(self) -> None:
        resolved = _resolved(min_output_tokens=16000)
        assert resolved.output_limit(4096) == 16000

    def test_request_above_floor_is_kept(self) -> None:
        resolved = _resolved(min_output_tokens=16000)
        assert resolved.output_limit(20000) == 20000

    def test_ceiling_applies_after_the_floor(self) -> None:
        resolved = _resolved(min_output_tokens=16000, max_output_tokens=8000)
        assert resolved.output_limit(4096) == 8000

    def test_zero_floor_leaves_the_request_alone(self) -> None:
        resolved = _resolved(min_output_tokens=0)
        assert resolved.output_limit(4096) == 4096

    def test_resolved_model_is_frozen(self) -> None:
        with pytest.raises(ValidationError):
            _resolved().model = "other"  # type: ignore[misc]


class TestLookupOrdering:
    def test_unmatched_model_returns_none(self) -> None:
        catalog = ModelCatalog([_cap("openai", "gpt-4o")])
        assert catalog.lookup("openai", "gpt-9") is None

    def test_entries_of_other_providers_are_ignored(self) -> None:
        catalog = ModelCatalog([_cap("anthropic", "gpt-4o", tier=ModelTier.STRONG)])
        assert catalog.lookup("openai", "gpt-4o") is None

    def test_exact_entry_overlays_prefix_entry_regardless_of_order(self) -> None:
        catalog = ModelCatalog(
            [
                _cap("p", "m-1", tier=ModelTier.FRONTIER),
                _cap("p", "m", match_type="prefix", tier=ModelTier.MINIMAL),
            ]
        )
        found = catalog.lookup("p", "m-1")
        assert found is not None
        assert found.tier is ModelTier.FRONTIER

    def test_longer_prefix_overlays_shorter_prefix(self) -> None:
        catalog = ModelCatalog(
            [
                _cap("p", "m-1-", match_type="prefix", tier=ModelTier.STRONG),
                _cap("p", "m-", match_type="prefix", tier=ModelTier.MINIMAL),
            ]
        )
        found = catalog.lookup("p", "m-1-x")
        assert found is not None
        assert found.tier is ModelTier.STRONG

    def test_fields_unset_on_the_winner_come_from_the_loser(self) -> None:
        catalog = ModelCatalog(
            [
                _cap("p", "m", match_type="prefix", notes="family note"),
                _cap("p", "m-1", tier=ModelTier.STRONG),
            ]
        )
        found = catalog.lookup("p", "m-1")
        assert found is not None
        assert found.notes == "family note"

    def test_later_entry_wins_a_tie(self) -> None:
        catalog = ModelCatalog(
            [
                _cap("p", "m", tier=ModelTier.MINIMAL),
                _cap("p", "m", tier=ModelTier.STRONG),
            ]
        )
        found = catalog.lookup("p", "m")
        assert found is not None
        assert found.tier is ModelTier.STRONG

    def test_lookup_result_is_a_plain_overlay(self) -> None:
        catalog = ModelCatalog([_cap("p", "m", tier=ModelTier.STRONG)])
        found = catalog.lookup("p", "m")
        assert type(found) is CapabilityOverlay


class TestBuiltinCatalogLookup:
    """REQ-CAT-2: overlay order against the shipped data."""

    def test_opus_5_5_combines_family_rules_with_exact_prices(self) -> None:
        found = ModelCatalog.builtin().lookup("anthropic", "claude-opus-5-5")
        assert found is not None
        assert (
            found.tier,
            found.structured_output,
            found.accepts_sampling_params,
            found.min_output_tokens,
            found.input_price_per_mtok,
            found.output_price_per_mtok,
        ) == (
            ModelTier.FRONTIER,
            StructuredOutputMode.JSON_SCHEMA,
            False,
            16000,
            4.0,
            20.0,
        )

    def test_opus_4_7_prefix_overlays_the_generic_opus_4_prefix(self) -> None:
        found = ModelCatalog.builtin().lookup("anthropic", "claude-opus-4-7")
        assert found is not None
        assert found.structured_output is StructuredOutputMode.JSON_SCHEMA
        assert found.accepts_sampling_params is False

    def test_opus_4_6_keeps_forced_tool_and_sampling(self) -> None:
        found = ModelCatalog.builtin().lookup("anthropic", "claude-opus-4-6")
        assert found is not None
        assert (
            found.structured_output,
            found.accepts_sampling_params,
            found.min_output_tokens,
            found.input_price_per_mtok,
            found.output_price_per_mtok,
        ) == (StructuredOutputMode.TOOL, True, 0, 5.0, 25.0)

    def test_dated_variant_inherits_family_rules_without_prices(self) -> None:
        found = ModelCatalog.builtin().lookup("anthropic", "claude-sonnet-5-5-20261001")
        assert found is not None
        assert found.tier is ModelTier.STRONG
        assert found.accepts_sampling_params is False
        assert found.input_price_per_mtok is None

    def test_builtin_catalog_is_cached(self) -> None:
        assert ModelCatalog.builtin() is ModelCatalog.builtin()


class TestUnknownModels:
    """REQ-CAT-3: unknown models resolve with the supplied defaults."""

    def test_lookup_of_unknown_openai_model_returns_none(self) -> None:
        assert ModelCatalog.builtin().lookup("openai", "gpt-7-nova") is None

    def test_unknown_openai_model_uses_conservative_kind_defaults(self) -> None:
        resolved = ModelCatalog.builtin().resolve(
            "openai", "gpt-7-nova", defaults=OPENAI_DEFAULTS
        )
        assert (
            resolved.known,
            resolved.structured_output,
            resolved.accepts_sampling_params,
            resolved.token_param,
            resolved.min_output_tokens,
            resolved.input_price_per_mtok,
            resolved.output_price_per_mtok,
        ) == (
            False,
            StructuredOutputMode.JSON_SCHEMA,
            False,
            TokenParam.MAX_COMPLETION_TOKENS,
            16000,
            None,
            None,
        )

    def test_unknown_compatible_model_keeps_sampling_and_allows_fallback(
        self,
    ) -> None:
        resolved = ModelCatalog.builtin().resolve(
            "groq", "some-model", defaults=COMPATIBLE_DEFAULTS
        )
        assert (
            resolved.known,
            resolved.structured_output,
            resolved.allow_structured_fallback,
            resolved.accepts_sampling_params,
            resolved.token_param,
            resolved.min_output_tokens,
        ) == (
            False,
            StructuredOutputMode.JSON_SCHEMA,
            True,
            True,
            TokenParam.MAX_TOKENS,
            0,
        )

    @pytest.mark.parametrize(
        "missing",
        [
            "structured_output",
            "allow_structured_fallback",
            "accepts_sampling_params",
            "token_param",
            "min_output_tokens",
        ],
    )
    def test_resolve_rejects_defaults_with_a_required_field_unset(
        self, missing: str
    ) -> None:
        defaults = COMPATIBLE_DEFAULTS.model_copy(update={missing: None})
        with pytest.raises(ValueError, match=missing):
            ModelCatalog.builtin().resolve("groq", "some-model", defaults=defaults)

    def test_resolve_rejects_defaults_even_when_the_entry_would_supply_the_field(
        self,
    ) -> None:
        defaults = COMPATIBLE_DEFAULTS.model_copy(update={"structured_output": None})
        with pytest.raises(ValueError, match="structured_output"):
            ModelCatalog.builtin().resolve(
                "anthropic", "claude-opus-5-5", defaults=defaults
            )


class TestResolve:
    def test_known_entry_sets_the_known_flag(self) -> None:
        resolved = ModelCatalog.builtin().resolve(
            "openai", "gpt-6.1-sol", defaults=OPENAI_DEFAULTS
        )
        assert resolved.known is True

    def test_entry_fields_override_the_defaults(self) -> None:
        resolved = ModelCatalog.builtin().resolve(
            "openai", "gpt-4o", defaults=OPENAI_DEFAULTS
        )
        assert resolved.accepts_sampling_params is True
        assert resolved.min_output_tokens == 0

    def test_defaults_fill_what_the_entry_leaves_unset(self) -> None:
        resolved = ModelCatalog.builtin().resolve(
            "openai", "gpt-6.1-sol", defaults=OPENAI_DEFAULTS
        )
        assert resolved.token_param is TokenParam.MAX_COMPLETION_TOKENS
        assert resolved.tier is ModelTier.STRONG

    def test_resolved_model_records_provider_and_model(self) -> None:
        resolved = ModelCatalog.builtin().resolve(
            "openai", "gpt-6.1-sol", defaults=OPENAI_DEFAULTS
        )
        assert (resolved.provider, resolved.model) == ("openai", "gpt-6.1-sol")

    def test_deprecated_defaults_to_false(self) -> None:
        resolved = ModelCatalog.builtin().resolve(
            "openai", "gpt-6.1-sol", defaults=OPENAI_DEFAULTS
        )
        assert resolved.deprecated is False

    def test_deprecated_entry_resolves_as_deprecated(self) -> None:
        resolved = ModelCatalog.builtin().resolve(
            "google", "gemini-2.5-pro", defaults=OPENAI_DEFAULTS
        )
        assert resolved.deprecated is True


class TestCanonicalAndVendorFallback:
    """REQ-CAT-4: canonical-provider and vendor-prefix fallbacks."""

    def test_custom_provider_falls_back_to_its_canonical_provider(self) -> None:
        catalog = ModelCatalog.builtin()
        found = catalog.lookup("my-proxy", "gpt-6.1-sol", canonical_provider="openai")
        assert found == catalog.lookup("openai", "gpt-6.1-sol")

    def test_custom_provider_without_canonical_provider_finds_nothing(self) -> None:
        assert ModelCatalog.builtin().lookup("my-proxy", "gpt-6.1-sol") is None

    def test_provider_own_entry_beats_the_canonical_provider(self) -> None:
        catalog = ModelCatalog(
            [
                _cap("openai", "m", tier=ModelTier.FRONTIER),
                _cap("my-proxy", "m", tier=ModelTier.MINIMAL),
            ]
        )
        found = catalog.lookup("my-proxy", "m", canonical_provider="openai")
        assert found is not None
        assert found.tier is ModelTier.MINIMAL

    def test_vendor_prefixed_model_keeps_only_vendor_neutral_facts(self) -> None:
        found = ModelCatalog.builtin().lookup("openrouter", "openai/gpt-6.1-sol")
        assert found is not None
        assert (found.tier, found.context_window) == (ModelTier.STRONG, 1_050_000)

    def test_vendor_prefixed_model_drops_prices_and_request_rules(self) -> None:
        found = ModelCatalog.builtin().lookup("openrouter", "openai/gpt-6.1-sol")
        assert found is not None
        assert (
            found.input_price_per_mtok,
            found.output_price_per_mtok,
            found.structured_output,
            found.accepts_sampling_params,
            found.token_param,
            found.min_output_tokens,
        ) == (None, None, None, None, None, None)

    def test_aggregator_entry_beats_vendor_fallback(self) -> None:
        found = ModelCatalog.builtin().lookup("openrouter", "openai/gpt-4o")
        assert found is not None
        assert (
            found.tier,
            found.input_price_per_mtok,
            found.output_price_per_mtok,
        ) == (ModelTier.STRONG, 2.5, 10.0)

    def test_unknown_vendor_prefix_finds_nothing(self) -> None:
        assert ModelCatalog.builtin().lookup("openrouter", "mistral/large") is None

    def test_known_vendor_with_unknown_inner_model_finds_nothing(self) -> None:
        assert ModelCatalog.builtin().lookup("openrouter", "openai/gpt-9") is None


class TestWithOverrides:
    """Field-level overlay of user entries (design section 4.2)."""

    def test_same_key_override_replaces_only_the_fields_it_sets(self) -> None:
        catalog = ModelCatalog.builtin().with_overrides(
            [_cap("openai", "gpt-6.1-sol", input_price_per_mtok=1.8)]
        )
        found = catalog.lookup("openai", "gpt-6.1-sol")
        assert found is not None
        assert (
            found.input_price_per_mtok,
            found.output_price_per_mtok,
            found.tier,
        ) == (1.8, 10.0, ModelTier.STRONG)

    def test_same_key_override_does_not_add_an_entry(self) -> None:
        base = ModelCatalog.builtin()
        extended = base.with_overrides([_cap("openai", "gpt-6.1-sol", tier="strong")])
        assert len(extended.entries) == len(base.entries)

    def test_new_key_is_appended(self) -> None:
        base = ModelCatalog.builtin()
        extended = base.with_overrides(
            [_cap("groq", "llama-3.3-70b-versatile", tier=ModelTier.EFFICIENT)]
        )
        found = extended.lookup("groq", "llama-3.3-70b-versatile")
        assert found is not None
        assert found.tier is ModelTier.EFFICIENT
        assert len(extended.entries) == len(base.entries) + 1

    def test_appended_overrides_keep_their_order(self) -> None:
        extended = ModelCatalog([]).with_overrides(
            [_cap("a", "m1"), _cap("b", "m2"), _cap("c", "m3")]
        )
        assert [entry.provider for entry in extended.entries] == ["a", "b", "c"]

    def test_later_override_of_the_same_new_key_wins(self) -> None:
        catalog = ModelCatalog([]).with_overrides(
            [
                _cap("groq", "m", tier=ModelTier.MINIMAL),
                _cap("groq", "m", tier=ModelTier.STRONG),
            ]
        )
        found = catalog.lookup("groq", "m")
        assert found is not None
        assert found.tier is ModelTier.STRONG

    def test_override_display_name_replaces_the_existing_one(self) -> None:
        base = ModelCatalog([_cap("p", "m", display_name="Old")])
        extended = base.with_overrides([_cap("p", "m", display_name="New")])
        assert extended.entries[0].display_name == "New"

    def test_override_without_display_name_keeps_the_existing_one(self) -> None:
        base = ModelCatalog([_cap("p", "m", display_name="Old")])
        extended = base.with_overrides([_cap("p", "m", tier=ModelTier.STRONG)])
        assert extended.entries[0].display_name == "Old"

    def test_base_catalog_is_left_untouched(self) -> None:
        base = ModelCatalog.builtin()
        before = base.entries
        base.with_overrides([_cap("openai", "gpt-6.1-sol", input_price_per_mtok=0.5)])
        assert base.entries == before

    def test_entries_are_exposed_as_a_tuple(self) -> None:
        assert isinstance(ModelCatalog([_cap("p", "m")]).entries, tuple)


class TestPriceFor:
    def test_provider_scoped_lookup_returns_both_prices(self) -> None:
        price = ModelCatalog.builtin().price_for("gpt-6.1-sol", provider="openai")
        assert price == (2.0, 10.0)

    def test_provider_scoped_lookup_ignores_other_providers(self) -> None:
        assert ModelCatalog.builtin().price_for("gpt-4o", provider="anthropic") is None

    def test_unscoped_lookup_searches_every_provider(self) -> None:
        assert ModelCatalog.builtin().price_for("gemini-4-argon") == (4.0, 20.0)

    def test_unscoped_lookup_matches_aggregator_model_ids(self) -> None:
        assert ModelCatalog.builtin().price_for("openai/gpt-4o") == (2.5, 10.0)

    def test_model_without_prices_returns_none(self) -> None:
        price = ModelCatalog.builtin().price_for("llama3.1:8b", provider="ollama")
        assert price is None

    def test_unknown_model_returns_none(self) -> None:
        assert ModelCatalog.builtin().price_for("unknown-model") is None

    def test_a_single_price_is_not_enough(self) -> None:
        catalog = ModelCatalog([_cap("p", "m", input_price_per_mtok=1.0)])
        assert catalog.price_for("m", provider="p") is None

    def test_prefix_rules_do_not_hide_exact_prices(self) -> None:
        price = ModelCatalog.builtin().price_for(
            "claude-opus-4-6", provider="anthropic"
        )
        assert price == (5.0, 25.0)

    def test_override_price_replaces_the_builtin_price(self) -> None:
        catalog = ModelCatalog.builtin().with_overrides(
            [_cap("openai", "gpt-6.1-sol", input_price_per_mtok=1.8)]
        )
        assert catalog.price_for("gpt-6.1-sol", provider="openai") == (1.8, 10.0)


class TestProvidersForModel:
    def test_openai_model_maps_to_openai(self) -> None:
        assert ModelCatalog.builtin().providers_for_model("gpt-4o") == ("openai",)

    def test_claude_model_maps_to_anthropic(self) -> None:
        providers = ModelCatalog.builtin().providers_for_model("claude-opus-5-5")
        assert providers == ("anthropic",)

    def test_gemini_model_maps_to_google(self) -> None:
        providers = ModelCatalog.builtin().providers_for_model("gemini-4-argon")
        assert providers == ("google",)

    def test_unknown_model_maps_to_nothing(self) -> None:
        assert ModelCatalog.builtin().providers_for_model("my-finetune") == ()

    def test_only_the_three_native_providers_are_reported(self) -> None:
        catalog = ModelCatalog(
            [_cap("groq", "shared"), _cap("ollama", "shared"), _cap("openai", "shared")]
        )
        assert catalog.providers_for_model("shared") == ("openai",)

    def test_providers_are_sorted_and_unique(self) -> None:
        catalog = ModelCatalog(
            [
                _cap("openai", "shared", match_type="prefix"),
                _cap("google", "shared"),
                _cap("openai", "shared"),
            ]
        )
        assert catalog.providers_for_model("shared") == ("google", "openai")
