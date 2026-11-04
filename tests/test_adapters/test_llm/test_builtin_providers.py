"""Tests for built-in provider data, kind defaults, and the builtin resolver."""

import pytest
from pydantic import ValidationError

from mkcv.adapters.llm.builtin_providers import (
    BUILTIN_PROVIDERS,
    CANONICAL_PROVIDER,
    KIND_DEFAULTS,
)
from mkcv.adapters.llm.model_resolver import builtin_resolver
from mkcv.adapters.llm.provider_spec import ProviderSpec
from mkcv.core.models.capability_overlay import CapabilityOverlay
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.model_tier import ModelTier
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.structured_output_mode import StructuredOutputMode
from mkcv.core.models.token_param import TokenParam

_REQUIRED_DEFAULT_FIELDS = (
    "structured_output",
    "allow_structured_fallback",
    "accepts_sampling_params",
    "token_param",
    "min_output_tokens",
)


class TestKindDefaults:
    """Design section 5.2: conservative defaults per provider kind."""

    @pytest.mark.parametrize("kind", list(ProviderKind))
    def test_every_kind_has_defaults(self, kind: ProviderKind) -> None:
        assert kind in KIND_DEFAULTS

    @pytest.mark.parametrize("kind", list(ProviderKind))
    def test_defaults_set_every_required_capability(self, kind: ProviderKind) -> None:
        defaults = KIND_DEFAULTS[kind]
        assert all(getattr(defaults, f) is not None for f in _REQUIRED_DEFAULT_FIELDS)

    @pytest.mark.parametrize("kind", list(ProviderKind))
    def test_every_kind_starts_with_json_schema(self, kind: ProviderKind) -> None:
        assert KIND_DEFAULTS[kind].structured_output is StructuredOutputMode.JSON_SCHEMA

    @pytest.mark.parametrize(
        ("kind", "token_param"),
        [
            (ProviderKind.ANTHROPIC, TokenParam.MAX_TOKENS),
            (ProviderKind.OPENAI, TokenParam.MAX_COMPLETION_TOKENS),
            (ProviderKind.GOOGLE, TokenParam.MAX_TOKENS),
            (ProviderKind.OPENAI_COMPATIBLE, TokenParam.MAX_TOKENS),
            (ProviderKind.STUB, TokenParam.MAX_TOKENS),
        ],
    )
    def test_token_param_per_kind(
        self, kind: ProviderKind, token_param: TokenParam
    ) -> None:
        assert KIND_DEFAULTS[kind].token_param is token_param

    @pytest.mark.parametrize(
        ("kind", "sampling", "floor", "fallback"),
        [
            (ProviderKind.ANTHROPIC, False, 16000, False),
            (ProviderKind.OPENAI, False, 16000, False),
            (ProviderKind.GOOGLE, False, 16000, False),
            (ProviderKind.OPENAI_COMPATIBLE, True, 0, True),
            (ProviderKind.STUB, True, 0, False),
        ],
    )
    def test_sampling_floor_and_fallback_per_kind(
        self, kind: ProviderKind, sampling: bool, floor: int, fallback: bool
    ) -> None:
        defaults = KIND_DEFAULTS[kind]
        assert (
            defaults.accepts_sampling_params,
            defaults.min_output_tokens,
            defaults.allow_structured_fallback,
        ) == (sampling, floor, fallback)

    def test_unknown_openai_model_resolves_conservatively(self) -> None:
        """REQ-CAT-3 repeated with the real constant."""
        resolved = ModelCatalog.builtin().resolve(
            "openai", "gpt-7-nova", defaults=KIND_DEFAULTS[ProviderKind.OPENAI]
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

    def test_unknown_compatible_model_resolves_permissively(self) -> None:
        """REQ-CAT-3 repeated with the real constant."""
        resolved = ModelCatalog.builtin().resolve(
            "groq",
            "some-model",
            defaults=KIND_DEFAULTS[ProviderKind.OPENAI_COMPATIBLE],
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


class TestCanonicalProvider:
    @pytest.mark.parametrize(
        ("kind", "canonical"),
        [
            (ProviderKind.ANTHROPIC, "anthropic"),
            (ProviderKind.OPENAI, "openai"),
            (ProviderKind.GOOGLE, "google"),
            (ProviderKind.OPENAI_COMPATIBLE, None),
            (ProviderKind.STUB, None),
        ],
    )
    def test_canonical_provider_per_kind(
        self, kind: ProviderKind, canonical: str | None
    ) -> None:
        assert CANONICAL_PROVIDER[kind] == canonical


class TestBuiltinProviders:
    def test_exactly_the_documented_providers_are_built_in(self) -> None:
        assert set(BUILTIN_PROVIDERS) == {
            "anthropic",
            "openai",
            "google",
            "openrouter",
            "ollama",
            "stub",
        }

    def test_every_spec_is_named_after_its_key(self) -> None:
        assert all(name == spec.name for name, spec in BUILTIN_PROVIDERS.items())

    def test_every_spec_is_flagged_builtin(self) -> None:
        assert all(spec.builtin for spec in BUILTIN_PROVIDERS.values())

    @pytest.mark.parametrize(
        ("name", "kind", "base_url", "api_key_env", "requires_api_key"),
        [
            ("anthropic", ProviderKind.ANTHROPIC, None, ("ANTHROPIC_API_KEY",), True),
            ("openai", ProviderKind.OPENAI, None, ("OPENAI_API_KEY",), True),
            (
                "google",
                ProviderKind.GOOGLE,
                None,
                ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
                True,
            ),
            (
                "openrouter",
                ProviderKind.OPENAI_COMPATIBLE,
                "https://openrouter.ai/api/v1",
                ("OPENROUTER_API_KEY",),
                True,
            ),
            (
                "ollama",
                ProviderKind.OPENAI_COMPATIBLE,
                "http://localhost:11434/v1",
                (),
                False,
            ),
            ("stub", ProviderKind.STUB, None, (), False),
        ],
    )
    def test_provider_wiring(
        self,
        name: str,
        kind: ProviderKind,
        base_url: str | None,
        api_key_env: tuple[str, ...],
        requires_api_key: bool,
    ) -> None:
        spec = BUILTIN_PROVIDERS[name]
        assert (
            spec.kind,
            spec.base_url,
            spec.api_key_env,
            spec.requires_api_key,
        ) == (kind, base_url, api_key_env, requires_api_key)

    def test_ollama_defaults_to_json_object_mode(self) -> None:
        ollama = BUILTIN_PROVIDERS["ollama"]
        assert ollama.defaults.structured_output is StructuredOutputMode.JSON_OBJECT

    def test_ollama_is_free(self) -> None:
        defaults = BUILTIN_PROVIDERS["ollama"].defaults
        assert (defaults.input_price_per_mtok, defaults.output_price_per_mtok) == (
            0.0,
            0.0,
        )

    @pytest.mark.parametrize(
        "name", ["anthropic", "openai", "google", "openrouter", "stub"]
    )
    def test_other_providers_add_no_defaults_of_their_own(self, name: str) -> None:
        assert BUILTIN_PROVIDERS[name].defaults == CapabilityOverlay()


class TestProviderSpec:
    def test_optional_fields_have_safe_defaults(self) -> None:
        spec = ProviderSpec(name="x", kind=ProviderKind.OPENAI_COMPATIBLE)
        assert (
            spec.base_url,
            spec.api_key_env,
            spec.api_key,
            spec.requires_api_key,
            spec.defaults,
            spec.builtin,
        ) == (None, (), None, True, CapabilityOverlay(), False)

    def test_spec_is_frozen(self) -> None:
        spec = ProviderSpec(name="x", kind=ProviderKind.OPENAI)
        with pytest.raises(ValidationError):
            spec.name = "y"  # type: ignore[misc]


class TestBuiltinResolver:
    def test_openai_resolver_uses_native_openai_rules(self) -> None:
        resolved = builtin_resolver(ProviderKind.OPENAI)("openai", "gpt-6.1-sol")
        assert (
            resolved.known,
            resolved.accepts_sampling_params,
            resolved.token_param,
            resolved.min_output_tokens,
            resolved.tier,
        ) == (
            True,
            False,
            TokenParam.MAX_COMPLETION_TOKENS,
            16000,
            ModelTier.STRONG,
        )

    def test_anthropic_resolver_keeps_forced_tool_for_claude_4(self) -> None:
        resolved = builtin_resolver(ProviderKind.ANTHROPIC)(
            "anthropic", "claude-sonnet-4-6"
        )
        assert resolved.structured_output is StructuredOutputMode.TOOL
        assert resolved.accepts_sampling_params is True

    def test_compatible_resolver_has_no_canonical_provider(self) -> None:
        resolved = builtin_resolver(ProviderKind.OPENAI_COMPATIBLE)(
            "my-proxy", "gpt-6.1-sol"
        )
        assert resolved.known is False

    def test_native_resolver_falls_back_to_the_canonical_provider(self) -> None:
        resolved = builtin_resolver(ProviderKind.OPENAI)("my-proxy", "gpt-6.1-sol")
        assert resolved.known is True

    def test_unknown_model_gets_the_kind_defaults(self) -> None:
        resolved = builtin_resolver(ProviderKind.GOOGLE)("google", "gemini-9")
        assert (
            resolved.known,
            resolved.accepts_sampling_params,
            resolved.min_output_tokens,
        ) == (False, False, 16000)

    def test_resolver_reports_the_requested_provider_name(self) -> None:
        resolved = builtin_resolver(ProviderKind.OPENAI_COMPATIBLE)("groq", "m")
        assert resolved.provider == "groq"
