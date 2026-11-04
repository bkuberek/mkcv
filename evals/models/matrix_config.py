"""The eval matrix: settings, judges, reference model, and models to evaluate."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.models.judge_config import JudgeConfig
from evals.models.matrix_model import MatrixModel
from evals.models.recommendation_settings import RecommendationSettings
from evals.models.run_settings import RunSettings


class MatrixConfig(BaseModel):
    """Everything ``evals/config/matrix.toml`` defines.

    The judges are a ``[[judges]]`` panel or, as before, one ``[judge]``
    table, which is a panel of one; ``panel`` returns them either way.

    ``models`` may be empty here: a run whose models all lack credentials is
    planned with none. ``load_matrix`` rejects a matrix file without models.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    run: RunSettings = Field(default_factory=RunSettings)
    judge: JudgeConfig | None = None
    judges: list[JudgeConfig] = Field(default_factory=list)
    reference: JudgeConfig
    models: list[MatrixModel]
    recommendation: RecommendationSettings = Field(
        default_factory=RecommendationSettings
    )

    @property
    def panel(self) -> list[JudgeConfig]:
        """The judges that score every judged output, in matrix order."""
        if self.judges:
            return list(self.judges)
        return [self.judge] if self.judge is not None else []

    @model_validator(mode="after")
    def _one_way_to_name_the_judges(self) -> "MatrixConfig":
        if self.judge is not None and self.judges:
            raise ValueError("name the judges with [judge] or [[judges]], not both")
        if not self.panel:
            raise ValueError("define the judges with [[judges]] (or one [judge])")
        _reject_repeats("judges", [judge.label for judge in self.panel])
        return self

    @model_validator(mode="after")
    def _models_are_unique(self) -> "MatrixConfig":
        _reject_repeats("models", [model.label for model in self.models])
        return self


def _reject_repeats(what: str, labels: list[str]) -> None:
    repeated = sorted({label for label in labels if labels.count(label) > 1})
    if repeated:
        raise ValueError(f"{what} listed more than once: {', '.join(repeated)}")
