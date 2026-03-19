"""Tests for ATSCheck model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.ats_check import ATSCheck


class TestATSCheck:
    """Tests for ATSCheck model."""

    def test_valid_all_passing(self) -> None:
        check = ATSCheck(
            single_column=True,
            no_tables=True,
            no_text_boxes=True,
            standard_headings=True,
            contact_in_body=True,
            standard_bullets=True,
            standard_fonts=True,
            text_extractable=True,
            reading_order_correct=True,
            overall_pass=True,
            issues=[],
        )
        assert check.overall_pass is True

    def test_valid_with_issues(self) -> None:
        check = ATSCheck(
            single_column=True,
            no_tables=False,
            no_text_boxes=True,
            standard_headings=True,
            contact_in_body=True,
            standard_bullets=True,
            standard_fonts=True,
            text_extractable=True,
            reading_order_correct=True,
            overall_pass=False,
            issues=["Contains tables that may not parse correctly"],
        )
        assert check.overall_pass is False

    def test_issues_list(self) -> None:
        issues = ["Non-standard fonts", "Text boxes detected"]
        check = ATSCheck(
            single_column=True,
            no_tables=True,
            no_text_boxes=False,
            standard_headings=True,
            contact_in_body=True,
            standard_bullets=True,
            standard_fonts=False,
            text_extractable=True,
            reading_order_correct=True,
            overall_pass=False,
            issues=issues,
        )
        assert check.issues == issues

    def test_single_column_required(self) -> None:
        with pytest.raises(ValidationError):
            ATSCheck(
                no_tables=True,  # type: ignore[call-arg]
                no_text_boxes=True,
                standard_headings=True,
                contact_in_body=True,
                standard_bullets=True,
                standard_fonts=True,
                text_extractable=True,
                reading_order_correct=True,
                overall_pass=True,
                issues=[],
            )

    def test_issues_required(self) -> None:
        with pytest.raises(ValidationError):
            ATSCheck(
                single_column=True,  # type: ignore[call-arg]
                no_tables=True,
                no_text_boxes=True,
                standard_headings=True,
                contact_in_body=True,
                standard_bullets=True,
                standard_fonts=True,
                text_extractable=True,
                reading_order_correct=True,
                overall_pass=True,
            )

    def test_model_dump_includes_all_fields(self) -> None:
        check = ATSCheck(
            single_column=True,
            no_tables=True,
            no_text_boxes=True,
            standard_headings=True,
            contact_in_body=True,
            standard_bullets=True,
            standard_fonts=True,
            text_extractable=True,
            reading_order_correct=True,
            overall_pass=True,
            issues=[],
        )
        data = check.model_dump()
        expected_keys = {
            "single_column",
            "no_tables",
            "no_text_boxes",
            "standard_headings",
            "contact_in_body",
            "standard_bullets",
            "standard_fonts",
            "text_extractable",
            "reading_order_correct",
            "overall_pass",
            "issues",
        }
        assert set(data.keys()) == expected_keys
