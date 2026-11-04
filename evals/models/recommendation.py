"""The models a run recommends for one stage and provider."""

from pydantic import BaseModel

from mkcv.core.models.stage_key import StageKey


class Recommendation(BaseModel):
    """Best, recommended, and economy model for a (stage, provider).

    The choices are model names and are all None when no model qualified;
    ``reason`` says why in either case.
    """

    stage: StageKey
    provider: str
    best: str | None = None
    recommended: str | None = None
    economy: str | None = None
    reason: str
