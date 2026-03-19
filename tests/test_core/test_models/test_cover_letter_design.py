"""Tests for CoverLetterDesign model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.cover_letter_design import CoverLetterDesign


class TestCoverLetterDesignDefaults:
    """Tests for default values."""

    def test_default_construction(self) -> None:
        design = CoverLetterDesign()
        assert design.page_size == "us-letter"
        assert design.margin_top == "1.2in"
        assert design.margin_bottom == "1in"
        assert design.margin_left == "1in"
        assert design.margin_right == "1in"
        assert design.font == "Source Sans Pro"
        assert design.font_size == "11pt"
        assert design.line_spacing == "0.7em"
        assert design.name_size == "16pt"
        assert design.default_salutation == "Dear Hiring Manager,"


class TestCoverLetterDesignValidation:
    """Tests for validation."""

    def test_valid_custom_margins(self) -> None:
        design = CoverLetterDesign(margin_left="1.25in", margin_right="1.25in")
        assert design.margin_left == "1.25in"

    def test_invalid_margin_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Invalid dimension"):
            CoverLetterDesign(margin_left="abc")


class TestIsPlaceholderCompany:
    """Tests for placeholder company detection."""

    @pytest.mark.parametrize(
        "name",
        [
            "",
            "Company",
            "Company Name",
            "Unknown",
            "N/A",
            "TBD",
            "General Purpose Resume",
            "General Purpose",
            "The Company",
            "Hiring Company",
        ],
    )
    def test_placeholder_names_detected(self, name: str) -> None:
        assert CoverLetterDesign.is_placeholder_company(name) is True

    @pytest.mark.parametrize(
        "name",
        ["Acme Corp", "Google", "Spotify", "AppliedXL", "DeepL"],
    )
    def test_real_companies_not_flagged(self, name: str) -> None:
        assert CoverLetterDesign.is_placeholder_company(name) is False

    def test_whitespace_stripped(self) -> None:
        assert CoverLetterDesign.is_placeholder_company("  Unknown  ") is True


class TestResolveSalutation:
    """Tests for resolve_salutation classmethod."""

    def test_uses_llm_salutation_when_present(self) -> None:
        result = CoverLetterDesign.resolve_salutation(
            salutation="Dear Ms. Johnson,",
            company="Acme",
        )
        assert result == "Dear Ms. Johnson,"

    def test_derives_from_company_when_no_salutation(self) -> None:
        result = CoverLetterDesign.resolve_salutation(
            salutation=None,
            company="Acme Corp",
        )
        assert result == "Dear Acme Corp Hiring Team,"

    def test_falls_back_to_default_when_no_company(self) -> None:
        result = CoverLetterDesign.resolve_salutation(
            salutation=None,
            company=None,
        )
        assert result == "Dear Hiring Manager,"

    def test_falls_back_when_company_is_placeholder(self) -> None:
        result = CoverLetterDesign.resolve_salutation(
            salutation=None,
            company="Unknown",
        )
        assert result == "Dear Hiring Manager,"

    def test_empty_salutation_triggers_fallback(self) -> None:
        result = CoverLetterDesign.resolve_salutation(
            salutation="",
            company="Spotify",
        )
        assert result == "Dear Spotify Hiring Team,"

    def test_whitespace_salutation_triggers_fallback(self) -> None:
        result = CoverLetterDesign.resolve_salutation(
            salutation="   ",
            company=None,
            default="To Whom It May Concern,",
        )
        assert result == "To Whom It May Concern,"

    def test_custom_default_used(self) -> None:
        result = CoverLetterDesign.resolve_salutation(
            salutation=None,
            company=None,
            default="To Whom It May Concern,",
        )
        assert result == "To Whom It May Concern,"
