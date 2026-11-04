"""The eval matrix: settings, judge, reference model, and models to evaluate."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.models.judge_config import JudgeConfig
from evals.models.matrix_model import MatrixModel
from evals.models.run_settings import RunSettings


class MatrixConfig(BaseModel):
    """Everything ``evals/config/matrix.toml`` defines."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run: RunSettings = Field(default_factory=RunSettings)
    judge: JudgeConfig
    reference: JudgeConfig
    models: list[MatrixModel] = Field(min_length=1)

    @model_validator(mode="after")
    def _models_are_unique(self) -> "MatrixConfig":
        labels = [model.label for model in self.models]
        repeated = sorted({label for label in labels if labels.count(label) > 1})
        if repeated:
            raise ValueError(f"models listed more than once: {', '.join(repeated)}")
        return self
