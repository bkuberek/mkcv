"""The estimated cost of a tournament run, round by round."""

from pydantic import BaseModel, Field

from evals.models.cost_estimate import CostEstimate


class TournamentEstimate(BaseModel):
    """Screening, the finals for the assumed survivors, and the worst case.

    The survivors are unknown before screening, so ``finals`` assumes the
    dearest model of each provider (then the next dearest, up to the number
    always kept) survives every stage; ``finals_worst_case`` keeps them all.
    """

    screening: CostEstimate
    finals: CostEstimate
    finals_worst_case: CostEstimate
    assumed_survivors: list[str] = Field(default_factory=list)

    @property
    def total_usd(self) -> float | None:
        """Screening plus the assumed finals, or None if either is unknown."""
        if self.screening.total_usd is None or self.finals.total_usd is None:
            return None
        return self.screening.total_usd + self.finals.total_usd
