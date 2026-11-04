"""A model to evaluate."""

from pydantic import BaseModel, ConfigDict, Field


class MatrixModel(BaseModel):
    """A provider and model, with an optional temperature for every stage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    model: str
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Overrides each stage's default temperature",
    )

    @property
    def label(self) -> str:
        """``provider/model``, as used in results and reports."""
        return f"{self.provider}/{self.model}"
