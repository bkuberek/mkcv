"""Load user model-capability overrides from configuration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from pydantic import ValidationError

from mkcv.core.exceptions.configuration import ConfigurationError
from mkcv.core.models.model_capability import ModelCapability
from mkcv.core.models.model_catalog import ModelCatalog

if TYPE_CHECKING:
    from mkcv.config.configuration import Configuration


def load_model_catalog(config: Configuration) -> ModelCatalog:
    """Return the built-in catalog with ``[[default.model_catalog]]`` applied.

    Entries from every configuration layer arrive in layer order (global,
    then workspace), so later entries overlay earlier ones field by field.

    Raises:
        ConfigurationError: If ``model_catalog`` is not an array of tables or
            an entry is not a valid ``ModelCapability``.
    """
    raw = config.get("model_catalog", [])
    if not isinstance(raw, list):
        raise ConfigurationError(
            "model_catalog must be an array of tables ([[default.model_catalog]])"
        )

    overrides = [_parse_entry(index, item) for index, item in enumerate(raw)]
    return ModelCatalog.builtin().with_overrides(overrides)


def _parse_entry(index: int, item: object) -> ModelCapability:
    label = f"Invalid [[default.model_catalog]] entry #{index + 1}"
    if not isinstance(item, Mapping):
        raise ConfigurationError(f"{label}: expected a table")
    try:
        return ModelCapability.model_validate(dict(item))
    except ValidationError as error:
        raise ConfigurationError(f"{label}: {error}") from error
