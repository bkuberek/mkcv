"""Entry layout configuration for resume rendering."""

from pydantic import BaseModel, field_validator

from mkcv.core.models.validators import validate_dimension


class EntryLayout(BaseModel):
    """Experience/education entry layout settings for RenderCV.

    All fields are optional. None means "use the RenderCV theme default".
    """

    date_and_location_width: str | None = None
    left_and_right_margin: str | None = None
    horizontal_space_between_connections: str | None = None

    @field_validator(
        "date_and_location_width",
        "left_and_right_margin",
        "horizontal_space_between_connections",
        mode="before",
    )
    @classmethod
    def check_dimension(cls, v: str | None) -> str | None:
        """Validate dimension values."""
        return validate_dimension(v)

    def to_rendercv_dict(self) -> dict[str, str]:
        """Build a dict of non-None fields for RenderCV's entries section."""
        result: dict[str, str] = {}
        if self.date_and_location_width is not None:
            result["date_and_location_width"] = self.date_and_location_width
        if self.left_and_right_margin is not None:
            result["left_and_right_margin"] = self.left_and_right_margin
        if self.horizontal_space_between_connections is not None:
            result["horizontal_space_between_connections"] = (
                self.horizontal_space_between_connections
            )
        return result
