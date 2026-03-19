"""Theme metadata model for resume themes."""

from typing import Literal

from pydantic import BaseModel


class ThemeInfo(BaseModel):
    """Metadata about an available resume theme."""

    name: str
    description: str
    font_family: str
    primary_color: str
    accent_color: str
    page_size: str
    source: Literal["built-in", "custom"] = "built-in"
