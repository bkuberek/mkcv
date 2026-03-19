"""Tests for HeaderLayout model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.header_layout import HeaderLayout


class TestHeaderLayoutDefaults:
    """Tests for default values."""

    def test_default_all_none(self) -> None:
        layout = HeaderLayout()
        assert layout.space_below_name is None
        assert layout.space_below_headline is None
        assert layout.space_below_connections is None


class TestHeaderLayoutValidation:
    """Tests for spacing validation."""

    def test_valid_spacing_accepted(self) -> None:
        layout = HeaderLayout(space_below_name="0.15cm")
        assert layout.space_below_name == "0.15cm"

    def test_invalid_spacing_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Invalid dimension"):
            HeaderLayout(space_below_name="bad")


class TestHeaderLayoutToRendercvDict:
    """Tests for to_rendercv_dict method."""

    def test_all_none_produces_empty_dict(self) -> None:
        assert HeaderLayout().to_rendercv_dict() == {}

    def test_non_none_fields_included(self) -> None:
        layout = HeaderLayout(space_below_name="0.2cm", space_below_headline="0.1cm")
        result = layout.to_rendercv_dict()
        assert result == {
            "space_below_name": "0.2cm",
            "space_below_headline": "0.1cm",
        }
