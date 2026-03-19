"""Section title layout configuration for resume rendering."""

from pydantic import BaseModel, field_validator

from mkcv.core.models.validators import validate_dimension

VALID_SECTION_TITLE_TYPES = (
    "with-parial-line",
    "with-full-line",
    "moderncv",
    "no-line",
)


class SectionTitleLayout(BaseModel):
    """Section title style settings for RenderCV.

    All fields are optional. None means "use the RenderCV theme default".
    """

    type: str | None = None
    space_above: str | None = None
    space_below: str | None = None

    @field_validator("type", mode="before")
    @classmethod
    def check_type(cls, v: str | None) -> str | None:
        """Validate section title type."""
        if v is not None and v not in VALID_SECTION_TITLE_TYPES:
            raise ValueError(
                f"Invalid section title type '{v}'. "
                f"Supported: {', '.join(VALID_SECTION_TITLE_TYPES)}"
            )
        return v

    @field_validator("space_above", "space_below", mode="before")
    @classmethod
    def check_dimension(cls, v: str | None) -> str | None:
        """Validate spacing values match dimension pattern."""
        return validate_dimension(v)

    def to_rendercv_dict(self) -> dict[str, str]:
        """Build a dict of non-None fields for RenderCV's section_titles."""
        result: dict[str, str] = {}
        if self.type is not None:
            result["type"] = self.type
        if self.space_above is not None:
            result["space_above"] = self.space_above
        if self.space_below is not None:
            result["space_below"] = self.space_below
        return result
