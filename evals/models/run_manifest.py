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
    judge: JudgeConfig
    catalog_prices: dict[str, tuple[float, float]] = Field(
        default_factory=dict,
        description="'provider/model' to (input, output) USD per 1M tokens",
    )
    cases: list[str] = Field(default_factory=list)
    skipped_models: list[str] = Field(
        default_factory=list,
        description="'provider/model: reason' for models that did not run",
    )
    judge_skipped: str | None = Field(
        default=None,
        description="Why the judge did not run (no API key), if it did not",
    )
