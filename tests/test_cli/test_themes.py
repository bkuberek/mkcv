"""Tests for the mkcv themes command."""

from unittest.mock import patch

from rich.console import Console

from mkcv.cli.commands.themes import (
    _render_preview_panel,
    _render_theme_table,
    themes_command,
)
from mkcv.core.models.theme_info import ThemeInfo


def _make_theme(
    name: str = "classic",
    description: str = "Traditional layout",
    font_family: str = "Source Sans 3",
    primary_color: str = "#004f90",
    accent_color: str = "#004f90",
    page_size: str = "us-letter",
) -> ThemeInfo:
    """Create a ThemeInfo with sensible defaults for testing."""
    return ThemeInfo(
        name=name,
        description=description,
        font_family=font_family,
        primary_color=primary_color,
        accent_color=accent_color,
        page_size=page_size,
    )


SAMPLE_THEMES = [
    _make_theme(name="classic", description="Traditional layout"),
    _make_theme(
        name="sb2nov",
        description="Single-column tech layout",
        font_family="New Computer Modern",
        primary_color="#000000",
        accent_color="#000000",
    ),
    _make_theme(
        name="moderncv",
        description="Academic CV style",
        font_family="Fontin",
    ),
]

_DISCOVER_PATH = "mkcv.cli.commands.themes.discover_themes"
_GET_THEME_PATH = "mkcv.cli.commands.themes.get_theme"


class TestThemeListing:
    """Tests for theme listing output."""

    def test_themes_lists_all_available_themes(self, capsys: object) -> None:
        with patch(_DISCOVER_PATH, return_value=SAMPLE_THEMES):
            themes_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "classic" in captured.out
        assert "sb2nov" in captured.out
        assert "moderncv" in captured.out

    def test_themes_shows_descriptions(self, capsys: object) -> None:
        with patch(_DISCOVER_PATH, return_value=SAMPLE_THEMES):
            themes_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "Traditional layout" in captured.out
        assert "Single-column tech layout" in captured.out

    def test_themes_shows_font_names(self, capsys: object) -> None:
        with patch(_DISCOVER_PATH, return_value=SAMPLE_THEMES):
            themes_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "Source Sans 3" in captured.out
        assert "New Computer Modern" in captured.out

    def test_themes_shows_preview_hint(self, capsys: object) -> None:
        with patch(_DISCOVER_PATH, return_value=SAMPLE_THEMES):
            themes_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "--preview" in captured.out

    def test_themes_empty_when_rendercv_unavailable(self, capsys: object) -> None:
        with patch(_DISCOVER_PATH, return_value=[]):
            themes_command()

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "No themes available" in captured.out


class TestThemePreview:
    """Tests for the --preview flag."""

    def test_preview_shows_theme_details(self, capsys: object) -> None:
        theme = _make_theme(name="classic")
        with (
            patch(_DISCOVER_PATH, return_value=SAMPLE_THEMES),
            patch(_GET_THEME_PATH, return_value=theme),
        ):
            themes_command(preview="classic")

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "classic" in captured.out
        assert "Source Sans 3" in captured.out
        assert "#004f90" in captured.out

    def test_preview_shows_sample_layout(self, capsys: object) -> None:
        theme = _make_theme(name="sb2nov", primary_color="#000000")
        with (
            patch(_DISCOVER_PATH, return_value=SAMPLE_THEMES),
            patch(_GET_THEME_PATH, return_value=theme),
        ):
            themes_command(preview="sb2nov")

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "John Doe" in captured.out
        assert "Experience" in captured.out

    def test_preview_shows_render_hint(self, capsys: object) -> None:
        theme = _make_theme(name="classic")
        with (
            patch(_DISCOVER_PATH, return_value=SAMPLE_THEMES),
            patch(_GET_THEME_PATH, return_value=theme),
        ):
            themes_command(preview="classic")

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "mkcv render" in captured.out
        assert "--theme classic" in captured.out

    def test_preview_invalid_theme_exits_with_error(self, capsys: object) -> None:
        import pytest

        with (
            patch(_DISCOVER_PATH, return_value=SAMPLE_THEMES),
            patch(_GET_THEME_PATH, return_value=None),
            pytest.raises(SystemExit, match="2"),
        ):
            themes_command(preview="nonexistent")

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "Unknown theme" in captured.out

    def test_preview_invalid_theme_lists_available(self, capsys: object) -> None:
        import pytest

        with (
            patch(_DISCOVER_PATH, return_value=SAMPLE_THEMES),
            patch(_GET_THEME_PATH, return_value=None),
            pytest.raises(SystemExit),
        ):
            themes_command(preview="nonexistent")

        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "classic" in captured.out
        assert "sb2nov" in captured.out


class TestThemeTable:
    """Tests for the theme table rendering helper."""

    def test_table_has_three_columns(self) -> None:
        table = _render_theme_table(SAMPLE_THEMES)
        assert len(table.columns) == 3

    def test_table_has_correct_row_count(self) -> None:
        table = _render_theme_table(SAMPLE_THEMES)
        assert table.row_count == len(SAMPLE_THEMES)


class TestPreviewPanel:
    """Tests for the preview panel rendering helper."""

    def test_panel_contains_theme_name_in_title(self) -> None:
        theme = _make_theme(name="moderncv")
        panel = _render_preview_panel(theme)
        assert panel.title is not None
        assert "moderncv" in str(panel.title)

    def test_panel_contains_description_in_subtitle(self) -> None:
        theme = _make_theme(description="Academic CV style")
        panel = _render_preview_panel(theme)
        assert panel.subtitle is not None
        assert "Academic CV style" in str(panel.subtitle)

    def test_panel_renders_without_error(self) -> None:
        theme = _make_theme()
        panel = _render_preview_panel(theme)
        test_console = Console(file=None, force_terminal=True, width=80)
        # Rendering should not raise
        with test_console.capture():
            test_console.print(panel)


class TestThemeService:
    """Tests for theme discovery service functions."""

    def test_discover_themes_returns_all_rendercv_themes(self) -> None:
        from mkcv.core.services.theme import discover_themes

        themes = discover_themes()
        names = {t.name for t in themes}
        assert "classic" in names
        assert "sb2nov" in names
        assert "moderncv" in names
        assert "engineeringresumes" in names

    def test_discover_themes_sorted_by_name(self) -> None:
        from mkcv.core.services.theme import discover_themes

        themes = discover_themes()
        names = [t.name for t in themes]
        assert names == sorted(names)

    def test_get_theme_returns_matching_theme(self) -> None:
        from mkcv.core.services.theme import get_theme

        theme = get_theme("classic")
        assert theme is not None
        assert theme.name == "classic"

    def test_get_theme_case_insensitive(self) -> None:
        from mkcv.core.services.theme import get_theme

        theme = get_theme("Classic")
        assert theme is not None
        assert theme.name == "classic"

    def test_get_theme_returns_none_for_unknown(self) -> None:
        from mkcv.core.services.theme import get_theme

        assert get_theme("nonexistent") is None

    def test_discover_themes_empty_when_rendercv_missing(self) -> None:
        from mkcv.core.services.theme import discover_themes

        with patch(
            "mkcv.core.services.theme._rendercv_available",
            return_value=False,
        ):
            assert discover_themes() == []

    def test_theme_info_has_font_and_colors(self) -> None:
        from mkcv.core.services.theme import get_theme

        theme = get_theme("classic")
        assert theme is not None
        assert theme.font_family
        assert theme.primary_color.startswith("#")
        assert theme.accent_color.startswith("#")
        assert theme.page_size
