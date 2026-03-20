"""Tests for SectionTitleLayout model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.section_title_layout import (
    VALID_SECTION_TITLE_TYPES,
    SectionTitleLayout,
)


class TestSectionTitleLayoutDefaults:
    """Tests for default values."""

    def test_default_all_none(self) -> None:
        layout = SectionTitleLayout()
        assert layout.type is None
        assert layout.space_above is None
        assert layout.space_below is None


class TestSectionTitleLayoutValidation:
    """Tests for type and spacing validation."""

    @pytest.mark.parametrize("title_type", VALID_SECTION_TITLE_TYPES)
    def test_valid_types_accepted(self, title_type: str) -> None:
        layout = SectionTitleLayout(type=title_type)
        assert layout.type == title_type

    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Invalid section title type"):
            SectionTitleLayout(type="invalid")

    def test_valid_spacing_accepted(self) -> None:
        layout = SectionTitleLayout(space_above="0.3cm")
        assert layout.space_above == "0.3cm"


class TestSectionTitleLayoutToRendercvDict:
    """Tests for to_rendercv_dict method."""

    def test_all_none_produces_empty_dict(self) -> None:
        assert SectionTitleLayout().to_rendercv_dict() == {}

    def test_non_none_fields_included(self) -> None:
        layout = SectionTitleLayout(type="with_full_line", space_above="0.4cm")
        result = layout.to_rendercv_dict()
        assert result == {"type": "with_full_line", "space_above": "0.4cm"}
