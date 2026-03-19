"""Complete cover letter generation result."""

from datetime import datetime

from pydantic import BaseModel

from mkcv.core.models.stage_metadata import StageMetadata


class CoverLetterResult(BaseModel):
    """Complete result of a cover letter generation pipeline."""

    run_id: str
    timestamp: datetime
    company: str
    role_title: str
    stages: list[StageMetadata]
    total_cost_usd: float
    total_duration_seconds: float
    review_score: int
    output_paths: dict[str, str]
