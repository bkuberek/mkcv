"""Tests for EntryLayout model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.entry_layout import EntryLayout


class TestEntryLayoutDefaults:
    """Tests for default values."""

    def test_default_all_none(self) -> None:
        layout = EntryLayout()
        assert layout.date_and_location_width is None
        assert layout.left_and_right_margin is None


class TestEntryLayoutValidation:
    """Tests for dimension validation."""

    def test_valid_width_accepted(self) -> None:
        layout = EntryLayout(date_and_location_width="3.6cm")
        assert layout.date_and_location_width == "3.6cm"

    def test_invalid_width_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Invalid dimension"):
            EntryLayout(date_and_location_width="bad")


class TestEntryLayoutToRendercvDict:
    """Tests for to_rendercv_dict method."""

    def test_all_none_produces_empty_dict(self) -> None:
        assert EntryLayout().to_rendercv_dict() == {}

    def test_non_none_fields_included(self) -> None:
        layout = EntryLayout(date_and_location_width="3.6cm")
        result = layout.to_rendercv_dict()
        assert result == {"date_and_location_width": "3.6cm"}
