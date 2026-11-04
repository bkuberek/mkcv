"""How a run sends its model calls: provider batches or online: ``[batch]``."""

from pydantic import BaseModel, ConfigDict, Field


class BatchSettings(BaseModel):
    """Batch submission, flushing, polling, and the Vertex AI bucket.

    With ``enabled``, the stage and judge calls of many jobs wait in a queue
    per provider and model and go out as one provider batch when
    ``max_requests`` are queued or ``flush_seconds`` have passed since the
    first. Jobs then mostly wait, so ``concurrency`` replaces ``[run]
    concurrency``. Google batches run on Vertex AI and need
    ``google_gcs_bucket``; without it Google calls go online.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = False
    max_requests: int = Field(default=1000, ge=1)
    flush_seconds: float = Field(default=30.0, ge=0.0)
    poll_seconds: float = Field(default=30.0, ge=0.0)
    concurrency: int = Field(default=512, ge=1)
    google_gcs_bucket: str | None = Field(
        default=None, description="gs://bucket for Vertex AI batch input and output"
    )
