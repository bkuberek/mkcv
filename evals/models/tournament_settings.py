"""How a run screens models before the finals: ``[tournament]``."""

from pydantic import BaseModel, ConfigDict, Field


class TournamentSettings(BaseModel):
    """The two rounds of a run and the rule that eliminates models between them.

    Screening runs every model on ``screening_cases`` (plus every review
    probe) with ``screening_repeats`` repeats, graded like the finals by
    every judge of the panel but the one from the model's own provider. A
    model leaves a stage only when it fails a hard gate or its primary
    score trails the leader's by more than ``margin`` plus the noise of that
    lead; the top ``keep_top`` models of each stage and the best
    ``keep_per_provider`` of each provider always go on. The finals run the
    survivors on every case with the whole judge panel and ``[run] repeats``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = True
    screening_cases: list[str] = Field(
        default_factory=list,
        description="Case IDs to screen on; empty screens every case",
    )
    screening_repeats: int = Field(default=1, ge=1)
    margin: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="How far behind the leader, beyond the noise, eliminates",
    )
    keep_top: int = Field(default=3, ge=1)
    keep_per_provider: int = Field(default=1, ge=0)
