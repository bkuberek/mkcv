"""Tests for ReviewReport model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.ats_check import ATSCheck
from mkcv.core.models.bullet_review import BulletReview
from mkcv.core.models.keyword_coverage import KeywordCoverage
from mkcv.core.models.review_report import ReviewReport


def _make_ats_check(overall_pass: bool = True) -> ATSCheck:
    return ATSCheck(
        single_column=True,
        no_tables=True,
        no_text_boxes=True,
        standard_headings=True,
        contact_in_body=True,
        standard_bullets=True,
        standard_fonts=True,
        text_extractable=True,
        reading_order_correct=True,
        overall_pass=overall_pass,
        issues=[],
    )


def _make_keyword_coverage() -> KeywordCoverage:
    return KeywordCoverage(
        total_keywords=10,
        matched_keywords=8,
        coverage_percent=80.0,
        missing_keywords=["Terraform"],
        suggestions=["Add Terraform experience"],
    )


def _make_bullet_review() -> BulletReview:
    return BulletReview(
        bullet_text="Led migration of microservices",
        classification="faithful",
    )


class TestReviewReport:
    """Tests for ReviewReport model."""

    def test_valid_creation(self) -> None:
        report = ReviewReport(
            overall_score=85,
            bullet_reviews=[_make_bullet_review()],
            keyword_coverage=_make_keyword_coverage(),
            ats_check=_make_ats_check(),
            tone_consistency="Consistent professional tone throughout",
            section_balance="Good balance across sections",
            length_assessment="Appropriate length for experience level",
            top_suggestions=["Quantify more achievements"],
            low_confidence_items=["Role at Startup X needs verification"],
        )
        assert report.overall_score == 85

    def test_overall_score_zero(self) -> None:
        report = ReviewReport(
            overall_score=0,
            bullet_reviews=[],
            keyword_coverage=_make_keyword_coverage(),
            ats_check=_make_ats_check(),
            tone_consistency="N/A",
            section_balance="N/A",
            length_assessment="N/A",
            top_suggestions=[],
            low_confidence_items=[],
        )
        assert report.overall_score == 0

    def test_overall_score_100(self) -> None:
        report = ReviewReport(
            overall_score=100,
            bullet_reviews=[],
            keyword_coverage=_make_keyword_coverage(),
            ats_check=_make_ats_check(),
            tone_consistency="Perfect",
            section_balance="Perfect",
            length_assessment="Perfect",
            top_suggestions=[],
            low_confidence_items=[],
        )
        assert report.overall_score == 100

    def test_overall_score_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReviewReport(
                overall_score=-1,
                bullet_reviews=[],
                keyword_coverage=_make_keyword_coverage(),
                ats_check=_make_ats_check(),
                tone_consistency="N/A",
                section_balance="N/A",
                length_assessment="N/A",
                top_suggestions=[],
                low_confidence_items=[],
            )

    def test_overall_score_above_100_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReviewReport(
                overall_score=101,
                bullet_reviews=[],
                keyword_coverage=_make_keyword_coverage(),
                ats_check=_make_ats_check(),
                tone_consistency="N/A",
                section_balance="N/A",
                length_assessment="N/A",
                top_suggestions=[],
                low_confidence_items=[],
            )

    def test_empty_bullet_reviews_allowed(self) -> None:
        report = ReviewReport(
            overall_score=70,
            bullet_reviews=[],
            keyword_coverage=_make_keyword_coverage(),
            ats_check=_make_ats_check(),
            tone_consistency="Good",
            section_balance="Good",
            length_assessment="Good",
            top_suggestions=[],
            low_confidence_items=[],
        )
        assert report.bullet_reviews == []

    def test_multiple_bullet_reviews(self) -> None:
        reviews = [
            BulletReview(
                bullet_text="Built platform",
                classification="faithful",
            ),
            BulletReview(
                bullet_text="Scaled to 1M users",
                classification="enhanced",
                explanation="Generalized from 800K",
            ),
        ]
        report = ReviewReport(
            overall_score=75,
            bullet_reviews=reviews,
            keyword_coverage=_make_keyword_coverage(),
            ats_check=_make_ats_check(),
            tone_consistency="Good",
            section_balance="Good",
            length_assessment="Good",
            top_suggestions=[],
            low_confidence_items=[],
        )
        assert len(report.bullet_reviews) == 2

    def test_tone_consistency_required(self) -> None:
        with pytest.raises(ValidationError):
            ReviewReport(
                overall_score=85,  # type: ignore[call-arg]
                bullet_reviews=[],
                keyword_coverage=_make_keyword_coverage(),
                ats_check=_make_ats_check(),
                section_balance="Good",
                length_assessment="Good",
                top_suggestions=[],
                low_confidence_items=[],
            )

    def test_model_dump_includes_all_fields(self) -> None:
        report = ReviewReport(
            overall_score=85,
            bullet_reviews=[],
            keyword_coverage=_make_keyword_coverage(),
            ats_check=_make_ats_check(),
            tone_consistency="Good",
            section_balance="Good",
            length_assessment="Good",
            top_suggestions=["Add metrics"],
            low_confidence_items=[],
        )
        data = report.model_dump()
        expected_keys = {
            "overall_score",
            "bullet_reviews",
            "keyword_coverage",
            "ats_check",
            "tone_consistency",
            "section_balance",
            "length_assessment",
            "top_suggestions",
            "low_confidence_items",
        }
        assert set(data.keys()) == expected_keys
