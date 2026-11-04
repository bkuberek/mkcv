"""Decide which matrix models can run with the credentials at hand."""

from collections.abc import Sequence

from evals.models.matrix_model import MatrixModel
from mkcv.adapters.llm.provider_registry import ProviderRegistry


def split_by_credentials(
    registry: ProviderRegistry, models: Sequence[MatrixModel]
) -> tuple[list[MatrixModel], list[str]]:
    """Split ``models`` into those that can run and the reasons for the rest.

    A model can run when its provider needs no key or a key is found (in the
    mkcv settings or the provider's environment variable). Without this check
    the registry would silently hand the model an offline stub.

    Returns:
        ``(runnable, skipped)``: runnable models in their original order, and
        one ``provider/model: reason`` line per skipped model.

    Raises:
        ConfigurationError: If a model names a provider mkcv does not know.
    """
    runnable: list[MatrixModel] = []
    skipped: list[str] = []
    for model in models:
        reason = missing_key_reason(registry, model.provider)
        if reason is None:
            runnable.append(model)
        else:
            skipped.append(f"{model.label}: {reason}")
    return runnable, skipped


def missing_key_reason(registry: ProviderRegistry, provider: str) -> str | None:
    """Return why ``provider`` cannot be called, or None if it can.

    Raises:
        ConfigurationError: If mkcv does not know the provider.
    """
    if registry.has_credentials(provider):
        return None
    hint = registry.credential_hint(provider)
    if registry.uses_vertex(provider):
        return f"no Application Default Credentials for provider '{provider}' ({hint})"
    return f"no API key for provider '{provider}' (set {hint})"
