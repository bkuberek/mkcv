"""Typography configuration for resume rendering."""

from pydantic import BaseModel, field_validator

from mkcv.core.models.validators import validate_dimension

VALID_ALIGNMENTS = ("justified", "left", "right", "center")


class TypographyLayout(BaseModel):
    """Typography settings that map to RenderCV's typography section.

    All fields are optional. None means "use the RenderCV theme default".
    Controls line spacing, text alignment, and per-element font sizes.
    """

    line_spacing: str | None = None
    alignment: str | None = None
    headline_size: str | None = None
    connections_size: str | None = None

    @field_validator("alignment", mode="before")
    @classmethod
    def check_alignment(cls, v: str | None) -> str | None:
        """Validate text alignment setting."""
        if v is not None and v not in VALID_ALIGNMENTS:
            raise ValueError(
                f"Invalid alignment '{v}'. Supported: {', '.join(VALID_ALIGNMENTS)}"
            )
        return v

    @field_validator("line_spacing", "headline_size", "connections_size", mode="before")
    @classmethod
    def check_dimension(cls, v: str | None) -> str | None:
        """Validate dimension values."""
        return validate_dimension(v)

    def to_rendercv_dict(self) -> dict[str, object]:
        """Build a dict of non-None fields for RenderCV's typography section."""
        result: dict[str, object] = {}
        if self.line_spacing is not None:
            result["line_spacing"] = self.line_spacing
        if self.alignment is not None:
            result["alignment"] = self.alignment
        # Per-element font sizes go into a nested font_size dict
        font_sizes: dict[str, str] = {}
        if self.headline_size is not None:
            font_sizes["headline"] = self.headline_size
        if self.connections_size is not None:
            font_sizes["connections"] = self.connections_size
        if font_sizes:
            result["font_size"] = font_sizes
        return result
