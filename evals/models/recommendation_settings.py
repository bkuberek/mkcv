"""How a run turns its scores into recommendations: ``[recommendation]``."""

from pydantic import BaseModel, ConfigDict, Field


class RecommendationSettings(BaseModel):
    """The cost tie-break and the tolerated fabrication rate.

    The defaults are what the shipped matrix uses: cost only decides between
    models whose quality scores are within 0.01 of each other, and a model
    that fabricates in any run is not eligible.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tie_epsilon: float = Field(
        default=0.01,
        ge=0.0,
        le=1.0,
        description="Scores this close to the best count as a tie broken by cost",
    )
    max_fabrication_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Highest share of runs with a fabricated claim a model may have",
    )
