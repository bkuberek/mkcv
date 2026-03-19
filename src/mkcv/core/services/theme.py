"""Theme discovery and preview service."""

from __future__ import annotations

import importlib.util
import logging
from typing import TYPE_CHECKING

from mkcv.core.models.theme_info import ThemeInfo

if TYPE_CHECKING:
    from pathlib import Path

    from mkcv.core.models.custom_theme import CustomTheme

logger = logging.getLogger(__name__)


def resolve_theme(
    cli_theme: str | None,
    config_theme: str,
    default: str = "sb2nov",
) -> str:
    """Resolve the effective theme from CLI flag, config, or default.

    Priority (highest to lowest):
        1. CLI --theme flag (explicit user intent)
        2. settings.rendering.theme (workspace or global config)
        3. Built-in default: "sb2nov"

    Args:
        cli_theme: Theme from CLI flag, or None if not provided.
        config_theme: Theme from configuration settings.
        default: Built-in fallback theme name.

    Returns:
        The resolved theme name.
    """
    if cli_theme is not None:
        return cli_theme
    return config_theme or default


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


def _discover_builtin_themes() -> list[ThemeInfo]:
    """Discover built-in themes from RenderCV.

    Returns:
        List of ThemeInfo for each built-in RenderCV theme.
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
                source="built-in",
            )
        )

    return themes


def load_custom_theme(theme_path: Path) -> CustomTheme:
    """Load and validate a custom theme YAML file.

    Args:
        theme_path: Path to the theme YAML file.

    Returns:
        Validated CustomTheme instance.

    Raises:
        ValidationError: If the theme YAML is invalid.
        FileNotFoundError: If the file doesn't exist.
    """
    from ruamel.yaml import YAML

    from mkcv.core.models.custom_theme import CustomTheme

    if not theme_path.is_file():
        raise FileNotFoundError(f"Theme file not found: {theme_path}")

    yaml = YAML()
    with theme_path.open("r", encoding="utf-8") as f:
        data = yaml.load(f)

    if data is None:
        data = {}

    # Derive name from filename stem if not in YAML
    if "name" not in data:
        data["name"] = theme_path.stem

    return CustomTheme.model_validate(data)


def discover_custom_themes(workspace_root: Path) -> list[ThemeInfo]:
    """Discover custom themes from workspace themes/ directory.

    Args:
        workspace_root: Path to the workspace root.

    Returns:
        List of ThemeInfo for valid custom themes.
        Invalid theme files are logged as warnings and skipped.
    """
    themes_dir = workspace_root / "themes"
    if not themes_dir.is_dir():
        return []

    builtin_names = {t.name for t in _discover_builtin_themes()}
    custom_themes: list[ThemeInfo] = []

    for yaml_file in sorted(themes_dir.glob("*.yaml")):
        try:
            custom = load_custom_theme(yaml_file)

            # Check for name collision with built-in themes
            if custom.name in builtin_names:
                logger.warning(
                    "Custom theme '%s' conflicts with built-in theme; skipping: %s",
                    custom.name,
                    yaml_file,
                )
                continue

            # Resolve base theme for defaults
            base = get_theme(custom.extends)
            custom_themes.append(
                ThemeInfo(
                    name=custom.name,
                    description=custom.description
                    or f"Custom theme based on {custom.extends}",
                    font_family=custom.overrides.get(
                        "font", base.font_family if base else ""
                    ),
                    primary_color=custom.overrides.get(
                        "primary_color", base.primary_color if base else ""
                    ),
                    accent_color=base.accent_color if base else "",
                    page_size=custom.overrides.get(
                        "page_size", base.page_size if base else "letterpaper"
                    ),
                    source="custom",
                )
            )
        except Exception:
            logger.warning("Invalid custom theme: %s", yaml_file, exc_info=True)

    return custom_themes


def discover_themes(
    workspace_root: Path | None = None,
) -> list[ThemeInfo]:
    """Discover all available themes (built-in + custom).

    Args:
        workspace_root: Optional workspace root for custom theme discovery.

    Returns:
        Sorted list of ThemeInfo for all available themes.
    """
    themes = _discover_builtin_themes()

    if workspace_root is not None:
        custom = discover_custom_themes(workspace_root)
        themes.extend(custom)

    return sorted(themes, key=lambda t: t.name)


def get_theme(
    name: str,
    workspace_root: Path | None = None,
) -> ThemeInfo | None:
    """Look up a single theme by name (built-in or custom).

    Args:
        name: Theme name (case-insensitive).
        workspace_root: Optional workspace root for custom theme lookup.

    Returns:
        ThemeInfo if found, None otherwise.
    """
    lower_name = name.lower()
    for theme in discover_themes(workspace_root):
        if theme.name.lower() == lower_name:
            return theme
    return None
