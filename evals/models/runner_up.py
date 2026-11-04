"""A model whose score is within the noise of a recommendation's winner."""

from pydantic import BaseModel, Field


class RunnerUp(BaseModel):
    """A model the winner does not clearly beat: its lead is under the noise."""

    label: str = Field(description="'provider/model'")
    score: float
    margin: float = Field(description="The winner's score minus this model's")
    noise: float | None = Field(
        description="Standard error of the winner's lead over this model"
    )
