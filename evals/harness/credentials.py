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
        if registry.has_credentials(model.provider):
            runnable.append(model)
        else:
            skipped.append(f"{model.label}: {_missing_key_reason(registry, model)}")
    return runnable, skipped


def _missing_key_reason(registry: ProviderRegistry, model: MatrixModel) -> str:
    variables = registry.get(model.provider).api_key_env
    where = (
        " or ".join(variables)
        if variables
        else f"api_key in [default.providers.{model.provider}]"
    )
    return f"no API key for provider '{model.provider}' (set {where})"
