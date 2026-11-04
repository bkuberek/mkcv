"""Registry of named LLM providers: specs, credentials, and adapter creation.

Providers are data (``ProviderSpec``): the built-in ones plus any a user
defines under ``[default.providers.<name>]``. Adapter creation dispatches on
the provider *kind*, never on a provider name.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from mkcv.adapters.llm.builtin_providers import (
    BUILTIN_PROVIDERS,
    CANONICAL_PROVIDER,
    KIND_DEFAULTS,
)
from mkcv.adapters.llm.provider_spec import ProviderSpec
from mkcv.adapters.llm.retry import RetryingLLMAdapter
from mkcv.core.exceptions.configuration import ConfigurationError
from mkcv.core.models.capability_overlay import CapabilityOverlay
from mkcv.core.models.provider_kind import ProviderKind

if TYPE_CHECKING:
    from mkcv.config.configuration import Configuration
    from mkcv.core.models.model_catalog import ModelCatalog
    from mkcv.core.models.resolved_model import ResolvedModel
    from mkcv.core.ports.llm import LLMPort

logger = logging.getLogger(__name__)

# Placeholder for providers that need no key but whose SDK requires a value.
_KEYLESS_API_KEY = "not-needed"

_PROVIDER_SETTING_KEYS = frozenset(
    {"type", "base_url", "api_key_env", "api_key", "requires_api_key"}
)
_CAPABILITY_KEYS = frozenset(CapabilityOverlay.model_fields)
_ALLOWED_SECTION_KEYS = _PROVIDER_SETTING_KEYS | _CAPABILITY_KEYS

_USER_PROVIDER_KINDS = (
    ProviderKind.ANTHROPIC,
    ProviderKind.OPENAI,
    ProviderKind.GOOGLE,
    ProviderKind.OPENAI_COMPATIBLE,
)


class ProviderRegistry:
    """Named providers and the model catalog their adapters resolve against."""

    def __init__(
        self, specs: Mapping[str, ProviderSpec], catalog: ModelCatalog
    ) -> None:
        self._specs = dict(specs)
        self._catalog = catalog

    @classmethod
    def from_config(
        cls, config: Configuration, catalog: ModelCatalog
    ) -> ProviderRegistry:
        """Build the registry from the built-ins plus ``[default.providers.*]``."""
        specs = dict(BUILTIN_PROVIDERS)
        section = config.get("providers", {})
        if not isinstance(section, Mapping):
            raise ConfigurationError(
                "providers must be a table of provider definitions "
                "([default.providers.<name>])"
            )
        for name, body in section.items():
            specs[name] = _spec_from_section(name, body, BUILTIN_PROVIDERS.get(name))
        return cls(specs, catalog)

    @property
    def catalog(self) -> ModelCatalog:
        """The model catalog adapters resolve capabilities against."""
        return self._catalog

    def names(self) -> tuple[str, ...]:
        """Return every provider name, sorted."""
        return tuple(sorted(self._specs))

    def get(self, name: str) -> ProviderSpec:
        """Return the spec for ``name``.

        Raises:
            ConfigurationError: If no provider has that name.
        """
        try:
            return self._specs[name]
        except KeyError:
            raise ConfigurationError(
                f"Unknown LLM provider '{name}'. "
                f"Known providers: {', '.join(self.names())}. "
                "Define new ones under [default.providers.<name>]."
            ) from None

    def resolve_api_key(self, name: str) -> str | None:
        """Return the key from config, else the first non-empty env variable."""
        spec = self.get(name)
        if spec.api_key:
            return spec.api_key
        for variable in spec.api_key_env:
            value = os.environ.get(variable)
            if value:
                return value
        return None

    def has_credentials(self, name: str) -> bool:
        """Return True if the provider needs no key or one can be resolved."""
        spec = self.get(name)
        return not spec.requires_api_key or self.resolve_api_key(name) is not None

    def defaults_for(self, name: str) -> CapabilityOverlay:
        """Return the provider-kind defaults overlaid with the provider's own."""
        spec = self.get(name)
        return KIND_DEFAULTS[spec.kind].overlay(spec.defaults)

    def resolve_model(self, name: str, model: str) -> ResolvedModel:
        """Resolve ``model``'s capabilities as served by provider ``name``."""
        spec = self.get(name)
        return self._catalog.resolve(
            name,
            model,
            defaults=self.defaults_for(name),
            canonical_provider=CANONICAL_PROVIDER[spec.kind],
        )

    def create_adapter(self, name: str, *, with_retry: bool = True) -> LLMPort:
        """Create the LLM adapter for provider ``name``.

        Falls back to the offline stub (with a warning) when the provider
        needs an API key and none is available.
        """
        spec = self.get(name)
        if spec.kind is ProviderKind.STUB:
            return _create_stub()

        api_key = self.resolve_api_key(name)
        if not api_key:
            if spec.requires_api_key:
                logger.warning(
                    "No API key for provider '%s'; falling back to stub.", name
                )
                return _create_stub()
            api_key = _KEYLESS_API_KEY

        adapter = _BUILDERS[spec.kind](spec, api_key, self)
        if with_retry:
            return RetryingLLMAdapter(adapter)
        return adapter


def _create_stub() -> LLMPort:
    from mkcv.adapters.llm.stub import StubLLMAdapter

    return StubLLMAdapter()


def _build_anthropic(
    spec: ProviderSpec, api_key: str, registry: ProviderRegistry
) -> LLMPort:
    from mkcv.adapters.llm.anthropic import AnthropicAdapter

    return AnthropicAdapter(
        api_key,
        base_url=spec.base_url,
        resolver=registry.resolve_model,
        provider_name=spec.name,
    )


def _build_openai(
    spec: ProviderSpec, api_key: str, registry: ProviderRegistry
) -> LLMPort:
    from mkcv.adapters.llm.openai import OpenAIAdapter

    return OpenAIAdapter(
        api_key,
        base_url=spec.base_url,
        resolver=registry.resolve_model,
        provider_name=spec.name,
    )


def _build_openai_compatible(
    spec: ProviderSpec, api_key: str, registry: ProviderRegistry
) -> LLMPort:
    from mkcv.adapters.llm.openai_compatible import OpenAICompatibleAdapter

    return OpenAICompatibleAdapter(
        api_key,
        base_url=spec.base_url,
        resolver=registry.resolve_model,
        provider_name=spec.name,
    )


def _build_google(
    spec: ProviderSpec, api_key: str, registry: ProviderRegistry
) -> LLMPort:
    from mkcv.adapters.llm.google import GoogleGeminiAdapter

    return GoogleGeminiAdapter(
        api_key,
        base_url=spec.base_url,
        resolver=registry.resolve_model,
        provider_name=spec.name,
    )


_BUILDERS: dict[
    ProviderKind, Callable[[ProviderSpec, str, ProviderRegistry], LLMPort]
] = {
    ProviderKind.ANTHROPIC: _build_anthropic,
    ProviderKind.OPENAI: _build_openai,
    ProviderKind.GOOGLE: _build_google,
    ProviderKind.OPENAI_COMPATIBLE: _build_openai_compatible,
}


def _spec_from_section(
    name: str, body: object, builtin: ProviderSpec | None
) -> ProviderSpec:
    """Build the spec for ``[default.providers.<name>]``.

    For a built-in provider the given values overlay the built-in spec; for a
    new provider the section defines it.
    """
    if not isinstance(body, Mapping):
        raise ConfigurationError(f"[default.providers.{name}] must be a table")

    kind = _kind_for(name, body, builtin)
    unknown = next((key for key in body if key not in _ALLOWED_SECTION_KEYS), None)
    if unknown is not None:
        raise ConfigurationError(
            f"Unknown key '{unknown}' in [default.providers.{name}]"
        )

    return ProviderSpec(
        name=name,
        kind=kind,
        base_url=_optional_text(
            name, body, "base_url", builtin.base_url if builtin else None
        ),
        api_key_env=(
            _key_variables(name, body["api_key_env"])
            if "api_key_env" in body
            else (builtin.api_key_env if builtin else ())
        ),
        api_key=_optional_text(
            name, body, "api_key", builtin.api_key if builtin else None
        ),
        requires_api_key=_flag(
            name,
            body,
            "requires_api_key",
            builtin.requires_api_key if builtin else True,
        ),
        defaults=_capability_defaults(name, body, builtin),
        builtin=builtin is not None,
    )


def _kind_for(
    name: str, body: Mapping[str, Any], builtin: ProviderSpec | None
) -> ProviderKind:
    declared = body.get("type")
    if declared is None:
        if builtin is not None:
            return builtin.kind
        raise ConfigurationError(
            f"Provider '{name}' needs type = \"openai-compatible\" "
            f"(or another provider kind) in [default.providers.{name}]"
        )

    try:
        kind = ProviderKind(declared)
    except ValueError:
        valid = ", ".join(kind.value for kind in _USER_PROVIDER_KINDS)
        raise ConfigurationError(
            f"Provider '{name}' has unknown type '{declared}'. Valid types: {valid}"
        ) from None

    if builtin is not None:
        if kind is not builtin.kind:
            raise ConfigurationError(
                f"Provider '{name}' is built in as '{builtin.kind}'; "
                "its type cannot be changed"
            )
        return kind

    if kind not in _USER_PROVIDER_KINDS:
        raise ConfigurationError(f"Provider '{name}' cannot use type '{kind}'")
    if kind is ProviderKind.OPENAI_COMPATIBLE and not body.get("base_url"):
        raise ConfigurationError(f"Provider '{name}' needs base_url")
    return kind


def _optional_text(
    name: str, body: Mapping[str, Any], key: str, fallback: str | None
) -> str | None:
    if key not in body:
        return fallback
    value = body[key]
    if not isinstance(value, str):
        raise ConfigurationError(
            f"{key} in [default.providers.{name}] must be a string"
        )
    return value


def _flag(name: str, body: Mapping[str, Any], key: str, fallback: bool) -> bool:
    if key not in body:
        return fallback
    value = body[key]
    if not isinstance(value, bool):
        raise ConfigurationError(
            f"{key} in [default.providers.{name}] must be true or false"
        )
    return value


def _key_variables(name: str, value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list | tuple) and all(isinstance(item, str) for item in value):
        return tuple(value)
    raise ConfigurationError(
        f"api_key_env in [default.providers.{name}] must be a string "
        "or a list of strings"
    )


def _capability_defaults(
    name: str, body: Mapping[str, Any], builtin: ProviderSpec | None
) -> CapabilityOverlay:
    given = {key: value for key, value in body.items() if key in _CAPABILITY_KEYS}
    try:
        overlay = CapabilityOverlay.model_validate(given)
    except ValidationError as error:
        raise ConfigurationError(
            f"Invalid capability setting in [default.providers.{name}]: {error}"
        ) from error
    return (builtin.defaults if builtin else CapabilityOverlay()).overlay(overlay)
