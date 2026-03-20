"""Tests for ResumeDesign model validation and helpers."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.entry_layout import EntryLayout
from mkcv.core.models.header_layout import HeaderLayout
from mkcv.core.models.page_layout import PageLayout
from mkcv.core.models.resume_design import (
    PAGE_SIZE_MAP,
    VALID_PAGE_SIZES,
    ResumeDesign,
)
from mkcv.core.models.section_title_layout import SectionTitleLayout
from mkcv.core.models.typography_layout import TypographyLayout


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

    def test_has_overrides_true_for_nested_page(self) -> None:
        design = ResumeDesign(page=PageLayout(left_margin="0.5in"))
        assert design.has_overrides() is True

    def test_has_overrides_true_for_nested_entries(self) -> None:
        design = ResumeDesign(entries=EntryLayout(date_and_location_width="3.6cm"))
        assert design.has_overrides() is True

    def test_has_overrides_true_for_nested_header(self) -> None:
        design = ResumeDesign(header=HeaderLayout(space_below_name="0.2cm"))
        assert design.has_overrides() is True


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

    def test_default_nested_sub_models_are_none(self) -> None:
        design = ResumeDesign()
        assert design.page is None
        assert design.header is None
        assert design.entries is None
        assert design.section_titles is None
        assert design.typography is None


class TestResumeDesignToRendercvDict:
    """Tests for to_rendercv_dict method."""

    def test_defaults_only_produce_theme(self) -> None:
        design = ResumeDesign()
        result = design.to_rendercv_dict()
        assert result == {"theme": "sb2nov"}

    def test_custom_font_at_top_level(self) -> None:
        design = ResumeDesign(font="Charter")
        result = design.to_rendercv_dict()
        assert result["font"] == "Charter"

    def test_custom_font_size_at_top_level(self) -> None:
        design = ResumeDesign(font_size="11pt")
        result = design.to_rendercv_dict()
        assert result["font_size"] == "11pt"

    def test_page_size_mapped(self) -> None:
        design = ResumeDesign(page_size="a4paper")
        result = design.to_rendercv_dict()
        assert result["page_size"] == "a4"

    def test_color_override(self) -> None:
        design = ResumeDesign(colors={"primary": "004080"})
        result = design.to_rendercv_dict()
        assert result["color"] == "004080"

    def test_nested_page_layout_emitted(self) -> None:
        design = ResumeDesign(
            page=PageLayout(left_margin="0.5in", right_margin="0.5in")
        )
        result = design.to_rendercv_dict()
        assert result["page"] == {
            "left_margin": "0.5in",
            "right_margin": "0.5in",
        }

    def test_nested_entries_layout_emitted(self) -> None:
        design = ResumeDesign(entries=EntryLayout(date_and_location_width="3.6cm"))
        result = design.to_rendercv_dict()
        assert result["entries"] == {"date_and_location_width": "3.6cm"}

    def test_nested_header_layout_emitted(self) -> None:
        design = ResumeDesign(header=HeaderLayout(space_below_name="0.15cm"))
        result = design.to_rendercv_dict()
        assert result["header"] == {"space_below_name": "0.15cm"}

    def test_nested_section_titles_emitted(self) -> None:
        design = ResumeDesign(section_titles=SectionTitleLayout(type="with_full_line"))
        result = design.to_rendercv_dict()
        assert result["section_titles"] == {"type": "with_full_line"}

    def test_nested_typography_emitted(self) -> None:
        design = ResumeDesign(typography=TypographyLayout(line_spacing="0.8em"))
        result = design.to_rendercv_dict()
        assert result["typography"] == {"line_spacing": "0.8em"}

    def test_empty_nested_model_not_emitted(self) -> None:
        design = ResumeDesign(page=PageLayout())
        result = design.to_rendercv_dict()
        assert "page" not in result

    def test_combined_flat_and_nested_overrides(self) -> None:
        design = ResumeDesign(
            font="Charter",
            page=PageLayout(left_margin="0.5in"),
            entries=EntryLayout(date_and_location_width="3.6cm"),
        )
        result = design.to_rendercv_dict()
        assert result["theme"] == "sb2nov"
        assert result["font"] == "Charter"
        assert result["page"] == {"left_margin": "0.5in"}
        assert result["entries"] == {"date_and_location_width": "3.6cm"}
