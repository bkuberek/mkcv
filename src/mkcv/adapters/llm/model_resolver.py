"""Resolve a model's capabilities for an adapter."""

from collections.abc import Callable

from mkcv.adapters.llm.builtin_providers import CANONICAL_PROVIDER, KIND_DEFAULTS
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.resolved_model import ResolvedModel

type ModelResolver = Callable[[str, str], ResolvedModel]
"""Maps ``(provider_name, model)`` to the model's resolved capabilities."""


def builtin_resolver(kind: ProviderKind) -> ModelResolver:
    """Return a resolver that uses the built-in catalog and ``kind``'s defaults.

    Adapters fall back to this when constructed without a resolver, which
    keeps direct construction in tests and scripts working.
    """
    catalog = ModelCatalog.builtin()
    defaults = KIND_DEFAULTS[kind]
    canonical_provider = CANONICAL_PROVIDER[kind]

    def resolve(provider: str, model: str) -> ResolvedModel:
        return catalog.resolve(
            provider,
            model,
            defaults=defaults,
            canonical_provider=canonical_provider,
        )

    return resolve
