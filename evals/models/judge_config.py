"""The model that judges outputs, or produces reference artifacts."""

from pydantic import BaseModel, ConfigDict


class JudgeConfig(BaseModel):
    """A provider and model used as the judge or the reference producer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    model: str

    @property
    def label(self) -> str:
        """``provider/model``, as used in results and reports."""
        return f"{self.provider}/{self.model}"
