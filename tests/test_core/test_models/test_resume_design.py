"""Tests for ResumeDesign model validation and helpers."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.resume_design import (
    PAGE_SIZE_MAP,
    VALID_PAGE_SIZES,
    ResumeDesign,
)


class TestResumeDesignPageSizeValidation:
    """Tests for page_size field validation."""

    def test_valid_page_sizes_accepted(self) -> None:
        for size in VALID_PAGE_SIZES:
            design = ResumeDesign(page_size=size)
            assert design.page_size == size

    def test_invalid_page_size_rejected(self) -> None:
        with pytest.raises(ValidationError, match="tabloid"):
            ResumeDesign(page_size="tabloid")

    def test_page_size_map_covers_all_valid_sizes(self) -> None:
        for size in VALID_PAGE_SIZES:
            assert size in PAGE_SIZE_MAP


class TestResumeDesignHasOverrides:
    """Tests for has_overrides method."""

    def test_has_overrides_false_for_defaults(self) -> None:
        design = ResumeDesign()
        assert design.has_overrides() is False

    def test_has_overrides_true_for_custom_font(self) -> None:
        design = ResumeDesign(font="Charter")
        assert design.has_overrides() is True

    def test_has_overrides_true_for_custom_page_size(self) -> None:
        design = ResumeDesign(page_size="a4paper")
        assert design.has_overrides() is True

    def test_has_overrides_true_for_custom_font_size(self) -> None:
        design = ResumeDesign(font_size="11pt")
        assert design.has_overrides() is True

    def test_has_overrides_true_for_custom_colors(self) -> None:
        design = ResumeDesign(colors={"primary": "004080"})
        assert design.has_overrides() is True

    def test_has_overrides_false_for_only_theme_change(self) -> None:
        design = ResumeDesign(theme="classic")
        assert design.has_overrides() is False


class TestResumeDesignDefaults:
    """Tests for default values."""

    def test_default_theme(self) -> None:
        design = ResumeDesign()
        assert design.theme == "sb2nov"

    def test_default_font(self) -> None:
        design = ResumeDesign()
        assert design.font == "SourceSansPro"

    def test_default_page_size(self) -> None:
        design = ResumeDesign()
        assert design.page_size == "letterpaper"

    def test_default_colors(self) -> None:
        design = ResumeDesign()
        assert design.colors == {"primary": "003366"}
