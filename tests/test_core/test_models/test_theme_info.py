"""Tests for ThemeInfo model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.theme_info import ThemeInfo


class TestThemeInfo:
    """Tests for ThemeInfo model."""

    def test_valid_creation(self) -> None:
        theme = ThemeInfo(
            name="classic",
            description="A clean, traditional resume layout",
            font_family="Times New Roman",
            primary_color="#003366",
            accent_color="#666666",
            page_size="letterpaper",
        )
        assert theme.name == "classic"

    def test_description_field(self) -> None:
        theme = ThemeInfo(
            name="modern",
            description="Contemporary design with bold typography",
            font_family="Helvetica",
            primary_color="#000000",
            accent_color="#0066CC",
            page_size="a4paper",
        )
        assert theme.description == "Contemporary design with bold typography"

    def test_font_family_field(self) -> None:
        theme = ThemeInfo(
            name="sb2nov",
            description="Default theme",
            font_family="SourceSansPro",
            primary_color="#003366",
            accent_color="#666666",
            page_size="letterpaper",
        )
        assert theme.font_family == "SourceSansPro"

    def test_primary_color_field(self) -> None:
        theme = ThemeInfo(
            name="bold",
            description="Bold theme",
            font_family="Arial",
            primary_color="#FF0000",
            accent_color="#000000",
            page_size="letterpaper",
        )
        assert theme.primary_color == "#FF0000"

    def test_accent_color_field(self) -> None:
        theme = ThemeInfo(
            name="minimal",
            description="Minimal theme",
            font_family="Courier",
            primary_color="#000000",
            accent_color="#999999",
            page_size="letterpaper",
        )
        assert theme.accent_color == "#999999"

    def test_page_size_field(self) -> None:
        theme = ThemeInfo(
            name="euro",
            description="European layout",
            font_family="Arial",
            primary_color="#003366",
            accent_color="#666666",
            page_size="a4paper",
        )
        assert theme.page_size == "a4paper"

    def test_name_required(self) -> None:
        with pytest.raises(ValidationError):
            ThemeInfo(
                description="A theme",  # type: ignore[call-arg]
                font_family="Arial",
                primary_color="#000",
                accent_color="#666",
                page_size="letterpaper",
            )

    def test_description_required(self) -> None:
        with pytest.raises(ValidationError):
            ThemeInfo(
                name="test",  # type: ignore[call-arg]
                font_family="Arial",
                primary_color="#000",
                accent_color="#666",
                page_size="letterpaper",
            )

    def test_all_fields_required(self) -> None:
        with pytest.raises(ValidationError):
            ThemeInfo()  # type: ignore[call-arg]

    def test_source_defaults_to_builtin(self) -> None:
        theme = ThemeInfo(
            name="classic",
            description="A theme",
            font_family="Arial",
            primary_color="#000",
            accent_color="#666",
            page_size="letterpaper",
        )
        assert theme.source == "built-in"

    def test_source_can_be_custom(self) -> None:
        theme = ThemeInfo(
            name="mytheme",
            description="Custom theme",
            font_family="Charter",
            primary_color="#004080",
            accent_color="#000",
            page_size="a4paper",
            source="custom",
        )
        assert theme.source == "custom"

    def test_model_dump(self) -> None:
        theme = ThemeInfo(
            name="classic",
            description="Traditional layout",
            font_family="Times New Roman",
            primary_color="#003366",
            accent_color="#666666",
            page_size="letterpaper",
        )
        data = theme.model_dump()
        assert data == {
            "name": "classic",
            "description": "Traditional layout",
            "font_family": "Times New Roman",
            "primary_color": "#003366",
            "accent_color": "#666666",
            "page_size": "letterpaper",
            "source": "built-in",
        }
