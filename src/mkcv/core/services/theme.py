"""Theme discovery and preview service."""

import importlib.util
import logging

from mkcv.core.models.theme_info import ThemeInfo

logger = logging.getLogger(__name__)

# Descriptions for built-in RenderCV themes. RenderCV does not expose
# descriptions programmatically, so these are maintained manually.
_THEME_DESCRIPTIONS: dict[str, str] = {
    "classic": "Traditional professional layout with partial-line section headers",
    "engineeringclassic": (
        "Engineering-focused variant of Classic with full-line headers"
    ),
    "engineeringresumes": "Minimal, dense layout optimized for engineering roles",
    "moderncv": "Academic/professional CV style inspired by LaTeX moderncv",
    "sb2nov": "Single-column, clean layout popular in tech (LaTeX sb2nov port)",
}

_FALLBACK_DESCRIPTION = "RenderCV built-in theme"


def _rendercv_available() -> bool:
    """Check whether rendercv is importable."""
    return importlib.util.find_spec("rendercv") is not None


def discover_themes() -> list[ThemeInfo]:
    """Discover available themes from RenderCV.

    Queries RenderCV's built-in theme registry and instantiates each
    theme to extract font, color, and page metadata.

    Returns:
        Sorted list of ThemeInfo for each available theme.
        Returns an empty list if RenderCV is not installed.
    """
    if not _rendercv_available():
        logger.warning("rendercv not installed; returning empty theme list")
        return []

    from rendercv.schema.models.design.built_in_design import (
        discover_other_themes,
    )
    from rendercv.schema.models.design.classic_theme import ClassicTheme

    theme_classes: list[type[ClassicTheme]] = [ClassicTheme, *discover_other_themes()]
    themes: list[ThemeInfo] = []

    for cls in theme_classes:
        instance = cls()
        name: str = instance.theme
        themes.append(
            ThemeInfo(
                name=name,
                description=_THEME_DESCRIPTIONS.get(name, _FALLBACK_DESCRIPTION),
                font_family=instance.typography.font_family.body,
                primary_color=instance.colors.name.as_hex(),
                accent_color=instance.colors.section_titles.as_hex(),
                page_size=instance.page.size,
            )
        )

    return sorted(themes, key=lambda t: t.name)


def get_theme(name: str) -> ThemeInfo | None:
    """Look up a single theme by name.

    Args:
        name: Theme name (case-insensitive).

    Returns:
        ThemeInfo if found, None otherwise.
    """
    lower_name = name.lower()
    for theme in discover_themes():
        if theme.name.lower() == lower_name:
            return theme
    return None
