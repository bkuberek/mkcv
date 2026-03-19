"""Per-run metadata written alongside versioned outputs."""

from datetime import datetime

from pydantic import BaseModel, Field


class RunMetadata(BaseModel):
    """Metadata for a single generation run (resume or cover letter).

    Written to ``.mkcv/run_metadata.json`` inside each version directory.
    """

    preset: str
    provider: str
    model: str
    timestamp: datetime = Field(default_factory=datetime.now)
    duration_seconds: float = 0.0
    review_score: int = 0
    total_cost_usd: float = 0.0
