"""Command-line choices that adjust the matrix for one run."""

from pydantic import BaseModel, ConfigDict, ValidationError

from evals.models.judge_config import JudgeConfig
from evals.models.matrix_config import MatrixConfig
from evals.models.matrix_model import MatrixModel
from evals.models.run_settings import RunSettings


class MatrixOverrides(BaseModel):
    """Values for ``--stages``, ``--cases``, ``--models``, ``--judge``,
    ``--concurrency``, and ``--single-round``; None (or False) leaves the
    matrix file's value in place."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stages: list[str] | None = None
    cases: list[str] | None = None
    models: list[str] | None = None
    judges: list[str] | None = None
    concurrency: int | None = None
    single_round: bool = False

    def apply(self, matrix: MatrixConfig) -> MatrixConfig:
        """Return ``matrix`` with the given overrides applied.

        ``--models`` replaces the model list: a model that the matrix already
        lists keeps its temperature, any other is added as given. ``--judge``
        replaces the whole judge panel.

        Raises:
            ValueError: If a value is invalid (unknown stage, a model or judge
                that is not ``provider:model``, a non-positive concurrency).
        """
        return MatrixConfig(
            run=self._run_settings(matrix.run),
            judge=matrix.judge if self.judges is None else None,
            judges=matrix.judges if self.judges is None else self._judges(),
            reference=matrix.reference,
            models=self._models(matrix.models),
            recommendation=matrix.recommendation,
            tournament=(
                matrix.tournament.model_copy(update={"enabled": False})
                if self.single_round
                else matrix.tournament
            ),
        )

    def _run_settings(self, current: RunSettings) -> RunSettings:
        changes = {
            name: value
            for name, value in (
                ("stages", self.stages),
                ("cases", self.cases),
                ("concurrency", self.concurrency),
            )
            if value is not None
        }
        try:
            return RunSettings.model_validate({**current.model_dump(), **changes})
        except ValidationError as error:
            raise ValueError(f"Invalid run setting: {error}") from error

    def _judges(self) -> list[JudgeConfig]:
        return [
            JudgeConfig(provider=provider, model=model)
            for provider, model in (
                _split_provider_model("--judge", value) for value in self.judges or []
            )
        ]

    def _models(self, current: list[MatrixModel]) -> list[MatrixModel]:
        if self.models is None:
            return current
        listed = {model.label: model for model in current}
        chosen: list[MatrixModel] = []
        for value in self.models:
            provider, model = _split_provider_model("--models", value)
            chosen.append(
                listed.get(f"{provider}/{model}")
                or MatrixModel(provider=provider, model=model)
            )
        return chosen


def _split_provider_model(flag: str, value: str) -> tuple[str, str]:
    """Split ``provider:model`` at the first colon (model IDs may hold more)."""
    provider, _, model = value.partition(":")
    if not provider or not model:
        raise ValueError(
            f"{flag} expects provider:model (for example openai:gpt-6.1-sol), "
            f"got '{value}'"
        )
    return provider, model
