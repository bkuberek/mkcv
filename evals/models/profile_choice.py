"""One stage's model in a suggested profile."""

from pydantic import BaseModel

from mkcv.core.models.stage_key import StageKey


class ProfileChoice(BaseModel):
    """The model a suggested profile runs a stage on, next to today's model.

    ``current`` is the built-in profile's model for the stage, or None for a
    profile that does not exist yet (``recommended``).
    """

    stage: StageKey
    provider: str
    model: str
    current: str | None = None
    score: float | None = None
    too_close_to_call: bool = False

    @property
    def changed(self) -> bool:
        """True when the suggestion differs from the profile's model today."""
        return self.model != self.current

    @property
    def label(self) -> str:
        """``provider/model``."""
        return f"{self.provider}/{self.model}"
