"""The model a run recommends for one stage, overall or within one provider."""

from pydantic import BaseModel, Field

from mkcv.core.models.stage_key import StageKey

OVERALL = "overall"
"""The ``scope`` of a recommendation that compares every provider's models."""


class Recommendation(BaseModel):
    """The best eligible model of a stage within a scope, and why.

    ``scope`` is ``"overall"`` or a provider name. ``provider``, ``model``,
    and ``score`` are None when no model qualified; ``reason`` says why in
    either case.
    """

    stage: StageKey
    scope: str
    provider: str | None = None
    model: str | None = None
    score: float | None = Field(
        default=None, description="The winner's primary quality score"
    )
    decided_by_cost: bool = Field(
        default=False,
        description="Other models scored within the tie epsilon; cost chose",
    )
    tied_with: list[str] = Field(
        default_factory=list,
        description="'provider/model' of the models the winner tied with",
    )
    reason: str

    @property
    def label(self) -> str | None:
        """``provider/model`` of the winner, or None without one."""
        if self.provider is None or self.model is None:
            return None
        return f"{self.provider}/{self.model}"
