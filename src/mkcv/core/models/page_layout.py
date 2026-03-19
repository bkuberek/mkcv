"""Page layout configuration for resume rendering."""

from pydantic import BaseModel, field_validator

from mkcv.core.models.validators import validate_dimension


class PageLayout(BaseModel):
    """Page-level layout settings that map to RenderCV's page design section.

    All fields are optional. None means "use the RenderCV theme default".
    """

    top_margin: str | None = None
    bottom_margin: str | None = None
    left_margin: str | None = None
    right_margin: str | None = None

    @field_validator(
        "top_margin", "bottom_margin", "left_margin", "right_margin", mode="before"
    )
    @classmethod
    def check_dimension(cls, v: str | None) -> str | None:
        """Validate margin values match dimension pattern."""
        return validate_dimension(v)

    def to_rendercv_dict(self) -> dict[str, str]:
        """Build a dict of non-None fields for RenderCV's page section."""
        result: dict[str, str] = {}
        if self.top_margin is not None:
            result["top_margin"] = self.top_margin
        if self.bottom_margin is not None:
            result["bottom_margin"] = self.bottom_margin
        if self.left_margin is not None:
            result["left_margin"] = self.left_margin
        if self.right_margin is not None:
            result["right_margin"] = self.right_margin
        return result
