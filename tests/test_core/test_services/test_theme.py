"""Tests for ThemeService: resolve_theme, parse_theme_argument, and discovery."""

from pathlib import Path
from unittest.mock import patch

import pytest

from mkcv.core.exceptions.render import RenderError
from mkcv.core.models.theme_info import ThemeInfo
from mkcv.core.services.theme import (
    discover_custom_themes,
    discover_themes,
    get_theme,
    load_custom_theme,
    parse_theme_argument,
    resolve_theme,
)


class TestResolveTheme:
    """Tests for resolve_theme function."""

    def test_resolve_theme_cli_wins(self) -> None:
        result = resolve_theme("moderncv", "classic")
        assert result == "moderncv"

    def test_resolve_theme_config_fallback(self) -> None:
        result = resolve_theme(None, "classic")
        assert result == "classic"

    def test_resolve_theme_default_fallback(self) -> None:
        result = resolve_theme(None, "")
        assert result == "sb2nov"

    def test_resolve_theme_empty_config_uses_default(self) -> None:
        result = resolve_theme(None, "")
        assert result == "sb2nov"

    def test_resolve_theme_cli_overrides_config_and_default(self) -> None:
        result = resolve_theme("engineeringresumes", "classic", default="sb2nov")
        assert result == "engineeringresumes"


class TestDiscoverCustomThemesEmptyDir:
    """Tests for custom theme discovery with empty or missing dirs."""

    def test_discover_custom_themes_empty_dir(self, tmp_path: Path) -> None:
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()
        result = discover_custom_themes(tmp_path)
        assert result == []

    def test_discover_custom_themes_no_dir(self, tmp_path: Path) -> None:
        result = discover_custom_themes(tmp_path)
        assert result == []


class TestDiscoverCustomThemesValidFile:
    """Tests for custom theme discovery with valid files."""

    def test_discover_custom_themes_valid_file(self, tmp_path: Path) -> None:
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()
        theme_file = themes_dir / "mytheme.yaml"
        theme_file.write_text(
            "name: mytheme\nextends: classic\ndescription: My theme\noverrides: {}\n",
            encoding="utf-8",
        )
        result = discover_custom_themes(tmp_path)
        assert len(result) == 1
        assert result[0].name == "mytheme"
        assert result[0].source == "custom"


class TestDiscoverCustomThemesInvalidFile:
    """Tests for custom theme discovery with invalid files."""

    def test_discover_custom_themes_invalid_file_skipped(self, tmp_path: Path) -> None:
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()
        bad_file = themes_dir / "broken.yaml"
        bad_file.write_text("name: BROKEN-UPPER\n", encoding="utf-8")
        result = discover_custom_themes(tmp_path)
        assert result == []


class TestDiscoverCustomThemesNameConflict:
    """Tests for name collision between custom and built-in themes."""

    def test_discover_custom_themes_name_conflict_with_builtin(
        self, tmp_path: Path
    ) -> None:
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()
        # "classic" is a built-in theme
        theme_file = themes_dir / "classic.yaml"
        theme_file.write_text(
            "name: classic\nextends: sb2nov\noverrides: {}\n",
            encoding="utf-8",
        )
        result = discover_custom_themes(tmp_path)
        assert result == []


class TestDiscoverCustomThemesNonYaml:
    """Tests that non-YAML files are ignored."""

    def test_discover_custom_themes_non_yaml_ignored(self, tmp_path: Path) -> None:
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()
        (themes_dir / "README.md").write_text("# Themes", encoding="utf-8")
        (themes_dir / ".DS_Store").write_text("", encoding="utf-8")
        result = discover_custom_themes(tmp_path)
        assert result == []


class TestDiscoverThemesMerge:
    """Tests for merging built-in and custom themes."""

    def test_discover_themes_merges_builtin_and_custom(self, tmp_path: Path) -> None:
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()
        theme_file = themes_dir / "mytheme.yaml"
        theme_file.write_text(
            "name: mytheme\nextends: classic\ndescription: Custom\noverrides: {}\n",
            encoding="utf-8",
        )
        result = discover_themes(workspace_root=tmp_path)
        names = [t.name for t in result]
        assert "mytheme" in names
        # Also should have built-in themes
        assert any(t.source == "built-in" for t in result)

    def test_get_theme_finds_custom_theme(self, tmp_path: Path) -> None:
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()
        theme_file = themes_dir / "mytheme.yaml"
        theme_file.write_text(
            "name: mytheme\nextends: classic\ndescription: Custom\noverrides: {}\n",
            encoding="utf-8",
        )
        result = get_theme("mytheme", workspace_root=tmp_path)
        assert result is not None
        assert result.name == "mytheme"


class TestLoadCustomTheme:
    """Tests for load_custom_theme function."""

    def test_load_valid_theme(self, tmp_path: Path) -> None:
        theme_file = tmp_path / "mytheme.yaml"
        content = (
            "name: mytheme\nextends: sb2nov\n"
            "description: test\noverrides:\n  font: Charter\n"
        )
        theme_file.write_text(content, encoding="utf-8")
        custom = load_custom_theme(theme_file)
        assert custom.name == "mytheme"
        assert custom.extends == "sb2nov"
        assert custom.overrides.get("font") == "Charter"

    def test_load_theme_derives_name_from_filename(self, tmp_path: Path) -> None:
        theme_file = tmp_path / "my-cool-theme.yaml"
        theme_file.write_text(
            "extends: classic\noverrides: {}\n",
            encoding="utf-8",
        )
        custom = load_custom_theme(theme_file)
        assert custom.name == "my-cool-theme"

    def test_load_nonexistent_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_custom_theme(tmp_path / "nonexistent.yaml")


def _make_theme_info(name: str) -> ThemeInfo:
    """Create a ThemeInfo with all required fields for testing."""
    return ThemeInfo(
        name=name,
        description=f"{name} theme",
        font_family="SourceSansPro",
        primary_color="#003366",
        accent_color="#003366",
        page_size="letterpaper",
        source="built-in",
    )


def _mock_themes() -> list[ThemeInfo]:
    """Return a fixed list of ThemeInfo for testing parse_theme_argument."""
    return [
        _make_theme_info("classic"),
        _make_theme_info("engineeringclassic"),
        _make_theme_info("engineeringresumes"),
        _make_theme_info("moderncv"),
        _make_theme_info("sb2nov"),
    ]


_DISCOVER_PATCH = "mkcv.core.services.theme.discover_themes"


class TestParseThemeArgument:
    """Tests for parse_theme_argument function."""

    @patch(_DISCOVER_PATCH, return_value=_mock_themes())
    def test_single_theme(self, _mock: object) -> None:
        result = parse_theme_argument("classic")
        assert result == ["classic"]

    @patch(_DISCOVER_PATCH, return_value=_mock_themes())
    def test_multiple_themes(self, _mock: object) -> None:
        result = parse_theme_argument("sb2nov,classic")
        assert result == ["sb2nov", "classic"]

    @patch(_DISCOVER_PATCH, return_value=_mock_themes())
    def test_all_keyword_expands(self, _mock: object) -> None:
        result = parse_theme_argument("all")
        assert len(result) == 5
        assert set(result) == {
            "classic",
            "engineeringclassic",
            "engineeringresumes",
            "moderncv",
            "sb2nov",
        }

    @patch(_DISCOVER_PATCH, return_value=_mock_themes())
    def test_all_case_insensitive(self, _mock: object) -> None:
        result = parse_theme_argument("ALL")
        assert len(result) == 5

    @patch(_DISCOVER_PATCH, return_value=_mock_themes())
    def test_whitespace_trimmed(self, _mock: object) -> None:
        result = parse_theme_argument(" sb2nov , classic ")
        assert result == ["sb2nov", "classic"]

    @patch(_DISCOVER_PATCH, return_value=_mock_themes())
    def test_empty_segments_ignored(self, _mock: object) -> None:
        result = parse_theme_argument("sb2nov,,classic,")
        assert result == ["sb2nov", "classic"]

    @patch(_DISCOVER_PATCH, return_value=_mock_themes())
    def test_deduplication_preserves_order(self, _mock: object) -> None:
        result = parse_theme_argument("classic,sb2nov,classic")
        assert result == ["classic", "sb2nov"]

    @patch(_DISCOVER_PATCH, return_value=_mock_themes())
    def test_case_insensitive_resolution(self, _mock: object) -> None:
        result = parse_theme_argument("SB2NOV")
        assert result == ["sb2nov"]

    @patch(_DISCOVER_PATCH, return_value=_mock_themes())
    def test_unknown_theme_raises_render_error(self, _mock: object) -> None:
        with pytest.raises(RenderError, match="nonexistent"):
            parse_theme_argument("nonexistent")

    @patch(_DISCOVER_PATCH, return_value=_mock_themes())
    def test_partial_unknown_raises_with_all_bad_names(self, _mock: object) -> None:
        with pytest.raises(RenderError) as exc_info:
            parse_theme_argument("sb2nov,bad1,classic,bad2")
        assert "bad1" in str(exc_info.value)
        assert "bad2" in str(exc_info.value)

    @patch(_DISCOVER_PATCH, return_value=_mock_themes())
    def test_empty_string_raises(self, _mock: object) -> None:
        with pytest.raises(RenderError):
            parse_theme_argument("")

    @patch(_DISCOVER_PATCH, return_value=_mock_themes())
    def test_all_mixed_with_names_raises(self, _mock: object) -> None:
        with pytest.raises(RenderError, match="cannot be combined"):
            parse_theme_argument("all,classic")
