"""The result of running one pipeline stage in isolation."""

from typing import Any, Literal

from pydantic import BaseModel

from mkcv.core.models.stage_metadata import StageMetadata


class StageRun(BaseModel):
    """Status, the stage's output, and its tokens, cost, and timing.

    ``payload`` is the parsed artifact for stages 1-3 and 5 and the YAML text
    for stage 4; it is None unless ``status`` is ``ok``.
    """

    status: Literal["ok", "error", "skipped"]
    error: str | None = None
    payload: dict[str, Any] | str | None = None
    metadata: StageMetadata | None = None
