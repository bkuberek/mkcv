"""Resume design/theme configuration model."""

from pydantic import BaseModel, Field


class ResumeDesign(BaseModel):
    """Design settings for resume rendering."""

    theme: str = "sb2nov"
    font: str = "SourceSansPro"
    font_size: str = "10pt"
    page_size: str = "letterpaper"
    colors: dict[str, str] = Field(default_factory=lambda: {"primary": "003366"})
