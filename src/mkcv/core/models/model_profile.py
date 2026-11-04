"""A named set of recommended models, one per stage."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from mkcv.core.models.stage_key import StageKey


class ModelProfile(BaseModel):
    """Recommended model for each stage, all served by one provider.

    An economy profile lists only the pipeline stages it changes and names
    the base profile it ``extends`` for every other stage.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    provider: str
    economy: bool = False
    extends: str | None = Field(
        default=None, description="Base profile for stages this one does not list"
    )
    evidence: Literal["provisional", "eval"] = Field(
        default="provisional",
        description="'eval' once an eval run backs the recommendations",
    )
    eval_run: str | None = Field(
        default=None, description="Identifier of the eval run behind the evidence"
    )
    stages: dict[StageKey, str] = Field(description="Stage to model ID")
