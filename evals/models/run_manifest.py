"""Metadata describing one eval run: ``run.json``."""

from datetime import datetime

from pydantic import BaseModel, Field

from evals.models.judge_config import JudgeConfig
from evals.models.matrix_config import MatrixConfig


class RunManifest(BaseModel):
    """What was run, with which prices, and which models could not run."""

    run_id: str
    started_at: datetime
    finished_at: datetime | None = None
    mkcv_version: str
    git_sha: str | None = None
    matrix: MatrixConfig
    judge: JudgeConfig | None = Field(
        default=None, description="The single judge of runs made before judge panels"
    )
    judges: list[JudgeConfig] = Field(
        default_factory=list, description="The judge panel the run asked for"
    )
    catalog_prices: dict[str, tuple[float, float]] = Field(
        default_factory=dict,
        description="'provider/model' to (input, output) USD per 1M tokens",
    )
    cases: list[str] = Field(default_factory=list)
    skipped_models: list[str] = Field(
        default_factory=list,
        description="'provider/model: reason' for models that did not run",
    )
    skipped_judges: dict[str, str] = Field(
        default_factory=dict,
        description="'provider/model' of each judge that did not run, and why",
    )
    judge_skipped: str | None = Field(
        default=None,
        description="Why the single judge of an older run did not run, if it did not",
    )

    @property
    def panel(self) -> list[JudgeConfig]:
        """The judges the run asked for (one, for a run before panels)."""
        if self.judges:
            return list(self.judges)
        return [self.judge] if self.judge is not None else []

    @property
    def judge_skip_reasons(self) -> dict[str, str]:
        """Why each judge that did not run was skipped, by ``provider/model``."""
        if self.skipped_judges:
            return dict(self.skipped_judges)
        if self.judge is not None and self.judge_skipped:
            return {self.judge.label: self.judge_skipped}
        return {}

    @property
    def judges_that_ran(self) -> list[str]:
        """``provider/model`` of each judge of the panel that ran."""
        skipped = self.judge_skip_reasons
        return [judge.label for judge in self.panel if judge.label not in skipped]
