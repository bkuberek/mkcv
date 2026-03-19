"""Tests for PageLayout model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.page_layout import PageLayout


class TestPageLayoutDefaults:
    """Tests for default values."""

    def test_default_all_none(self) -> None:
        layout = PageLayout()
        assert layout.top_margin is None
        assert layout.bottom_margin is None
        assert layout.left_margin is None
        assert layout.right_margin is None


class TestPageLayoutValidation:
    """Tests for margin validation."""

    def test_valid_margins_accepted(self) -> None:
        layout = PageLayout(
            top_margin="0.7in",
            left_margin="0.5in",
            right_margin="0.5in",
            bottom_margin="1cm",
        )
        assert layout.top_margin == "0.7in"
        assert layout.left_margin == "0.5in"

    def test_invalid_margin_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Invalid dimension"):
            PageLayout(left_margin="abc")

    def test_none_margin_allowed(self) -> None:
        layout = PageLayout(left_margin=None)
        assert layout.left_margin is None


class TestPageLayoutToRendercvDict:
    """Tests for to_rendercv_dict method."""

    def test_all_none_produces_empty_dict(self) -> None:
        assert PageLayout().to_rendercv_dict() == {}

    def test_non_none_fields_included(self) -> None:
        layout = PageLayout(left_margin="0.5in", right_margin="0.5in")
        result = layout.to_rendercv_dict()
        assert result == {"left_margin": "0.5in", "right_margin": "0.5in"}

    def test_partial_overrides(self) -> None:
        layout = PageLayout(top_margin="0.8in")
        result = layout.to_rendercv_dict()
        assert result == {"top_margin": "0.8in"}
