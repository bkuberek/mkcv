"""Custom theme definition model."""

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CustomTheme(BaseModel):
    """A user-defined theme loaded from workspace themes/ directory.

    Custom themes extend a built-in RenderCV theme with property
    overrides for font, colors, page size, etc. The applies_to field
    controls which document types this theme targets (resume, cover
    letter, or both).
    """

    name: str
    extends: str = "classic"
    description: str = ""
    applies_to: Literal["all", "resume", "cover_letter"] = "all"
    overrides: dict[str, str] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure theme name is lowercase alphanumeric with hyphens."""
        if not re.match(r"^[a-z][a-z0-9-]*$", v):
            raise ValueError(
                f"Theme name '{v}' must be lowercase alphanumeric "
                "with hyphens, starting with a letter."
            )
        return v
