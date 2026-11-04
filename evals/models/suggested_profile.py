"""A model profile the run suggests; nothing applies it automatically."""

from pydantic import BaseModel, Field

from evals.models.profile_choice import ProfileChoice


class SuggestedProfile(BaseModel):
    """A built-in provider profile, or the cross-provider ``recommended`` one.

    ``provider`` is the profile's provider, or None when each stage may use
    a different one.
    """

    name: str
    provider: str | None = None
    choices: list[ProfileChoice] = Field(default_factory=list)

    @property
    def changes(self) -> list[ProfileChoice]:
        """The choices that differ from the profile's models today."""
        return [choice for choice in self.choices if choice.changed]
