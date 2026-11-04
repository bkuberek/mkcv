"""The model chosen for one stage, and why."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.stage_config import StageConfig
from mkcv.core.models.stage_key import StageKey


class StageAssignment(BaseModel):
    """A resolved stage: provider, model, temperature, and where they came from."""

    model_config = ConfigDict(frozen=True)

    stage: StageKey
    provider: str
    provider_kind: ProviderKind
    model: str
    temperature: float
    source: Literal["cli", "config", "profile"]

    def to_stage_config(self) -> StageConfig:
        """Return the provider, model, and temperature as a ``StageConfig``."""
        return StageConfig(
            provider=self.provider,
            model=self.model,
            temperature=self.temperature,
        )
