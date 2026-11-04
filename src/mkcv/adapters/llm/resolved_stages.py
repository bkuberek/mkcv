"""The outcome of resolving which model each stage runs on."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from mkcv.core.models.model_profile import ModelProfile
from mkcv.core.models.stage_assignment import StageAssignment
from mkcv.core.models.stage_config import StageConfig
from mkcv.core.models.stage_key import PIPELINE_STAGE_NUMBERS, StageKey

type ProfileSource = Literal["cli", "config", "default", "preset"]
"""Where the active profile (or provider) came from."""


class ResolvedStages(BaseModel):
    """Assignments for the requested stages, plus the profile behind them."""

    model_config = ConfigDict(frozen=True)

    assignments: dict[StageKey, StageAssignment]
    profile: ModelProfile | None
    profile_source: ProfileSource
    preset_name: str

    def pipeline_stage_configs(self) -> dict[int, StageConfig]:
        """Return the resolved pipeline stages keyed by stage number (1 to 5)."""
        return {
            number: self.assignments[stage].to_stage_config()
            for stage, number in PIPELINE_STAGE_NUMBERS.items()
            if stage in self.assignments
        }
