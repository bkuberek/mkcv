"""Complete pipeline execution result."""

from datetime import datetime

from pydantic import BaseModel

from mkcv.core.models.stage_metadata import StageMetadata


class PipelineResult(BaseModel):
    """Complete result of a pipeline execution."""

    run_id: str
    timestamp: datetime
    jd_source: str
    kb_source: str
    company: str
    role_title: str
    stages: list[StageMetadata]
    total_cost_usd: float
    total_duration_seconds: float
    review_score: int
    output_paths: dict[str, str]
