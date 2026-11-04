"""A non-blocking warning about a stage's model or a provider."""

from pydantic import BaseModel, ConfigDict

from mkcv.core.models.model_warning_kind import ModelWarningKind
from mkcv.core.models.stage_key import StageKey


class ModelWarning(BaseModel):
    """One thing worth telling the user before a run starts."""

    model_config = ConfigDict(frozen=True)

    kind: ModelWarningKind
    stage: StageKey | None
    provider: str
    model: str | None
    message: str
