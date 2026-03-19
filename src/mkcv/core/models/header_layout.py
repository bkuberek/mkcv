"""Header layout configuration for resume rendering."""

from pydantic import BaseModel, field_validator

from mkcv.core.models.validators import validate_dimension


class HeaderLayout(BaseModel):
    """Header spacing settings that map to RenderCV's header design section.

    All fields are optional. None means "use the RenderCV theme default".
    """

    space_below_name: str | None = None
    space_below_headline: str | None = None
    space_below_connections: str | None = None

    @field_validator(
        "space_below_name",
        "space_below_headline",
        "space_below_connections",
        mode="before",
    )
    @classmethod
    def check_dimension(cls, v: str | None) -> str | None:
        """Validate spacing values match dimension pattern."""
        return validate_dimension(v)

    def to_rendercv_dict(self) -> dict[str, str]:
        """Build a dict of non-None fields for RenderCV's header section."""
        result: dict[str, str] = {}
        if self.space_below_name is not None:
            result["space_below_name"] = self.space_below_name
        if self.space_below_headline is not None:
            result["space_below_headline"] = self.space_below_headline
        if self.space_below_connections is not None:
            result["space_below_connections"] = self.space_below_connections
        return result
