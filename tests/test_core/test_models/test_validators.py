"""Tests for shared dimension validators."""

import pytest

from mkcv.core.models.validators import validate_dimension


class TestValidateDimension:
    """Tests for validate_dimension function."""

    def test_none_passes_through(self) -> None:
        assert validate_dimension(None) is None

    @pytest.mark.parametrize(
        "value",
        ["0.5in", "1in", "2.5cm", "10mm", "12pt", "0.7em", "1.2in", "0em"],
    )
    def test_valid_dimensions_accepted(self, value: str) -> None:
        assert validate_dimension(value) == value

    @pytest.mark.parametrize(
        "value",
        ["1px", "abc", "1.2.3in", "in", "cm", "", "10", "10 pt", "10PT"],
    )
    def test_invalid_dimensions_rejected(self, value: str) -> None:
        with pytest.raises(ValueError, match="Invalid dimension"):
            validate_dimension(value)
