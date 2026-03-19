"""Tests for TypographyLayout model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.typography_layout import VALID_ALIGNMENTS, TypographyLayout


class TestTypographyLayoutDefaults:
    """Tests for default values."""

    def test_default_all_none(self) -> None:
        layout = TypographyLayout()
        assert layout.line_spacing is None
        assert layout.alignment is None
        assert layout.headline_size is None
        assert layout.connections_size is None


class TestTypographyLayoutValidation:
    """Tests for validation."""

    @pytest.mark.parametrize("alignment", VALID_ALIGNMENTS)
    def test_valid_alignments_accepted(self, alignment: str) -> None:
        layout = TypographyLayout(alignment=alignment)
        assert layout.alignment == alignment

    def test_invalid_alignment_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Invalid alignment"):
            TypographyLayout(alignment="bad")

    def test_valid_line_spacing_accepted(self) -> None:
        layout = TypographyLayout(line_spacing="0.7em")
        assert layout.line_spacing == "0.7em"


class TestTypographyLayoutToRendercvDict:
    """Tests for to_rendercv_dict method."""

    def test_all_none_produces_empty_dict(self) -> None:
        assert TypographyLayout().to_rendercv_dict() == {}

    def test_line_spacing_included(self) -> None:
        layout = TypographyLayout(line_spacing="0.8em")
        result = layout.to_rendercv_dict()
        assert result == {"line_spacing": "0.8em"}

    def test_headline_size_nested_in_font_size(self) -> None:
        layout = TypographyLayout(headline_size="9pt")
        result = layout.to_rendercv_dict()
        assert result == {"font_size": {"headline": "9pt"}}

    def test_multiple_font_sizes_combined(self) -> None:
        layout = TypographyLayout(headline_size="9pt", connections_size="8pt")
        result = layout.to_rendercv_dict()
        assert result == {"font_size": {"headline": "9pt", "connections": "8pt"}}
