"""Tests for CoverLetterReview model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.cover_letter_review import CoverLetterReview


def _make_review(**overrides: object) -> CoverLetterReview:
    """Build a valid CoverLetterReview with sensible defaults."""
    defaults: dict[str, object] = {
        "overall_score": 85,
        "tone_assessment": "Professional and appropriate.",
        "specificity_score": 70,
        "keyword_alignment": ["Python", "AWS"],
        "length_assessment": "Good length for a cover letter.",
        "strengths": ["Strong opening", "Good specifics"],
        "improvements": ["Could mention leadership more"],
    }
    defaults.update(overrides)
    return CoverLetterReview(**defaults)  # type: ignore[arg-type]


class TestCoverLetterReviewRequiredFields:
    """Tests for required field validation."""

    def test_requires_overall_score(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetterReview(
                tone_assessment="Good",
                specificity_score=70,
                keyword_alignment=["Python"],
                length_assessment="Good",
                strengths=["Strong"],
                improvements=["More detail"],
            )  # type: ignore[call-arg]

    def test_requires_tone_assessment(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetterReview(
                overall_score=85,
                specificity_score=70,
                keyword_alignment=["Python"],
                length_assessment="Good",
                strengths=["Strong"],
                improvements=["More detail"],
            )  # type: ignore[call-arg]

    def test_requires_specificity_score(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetterReview(
                overall_score=85,
                tone_assessment="Good",
                keyword_alignment=["Python"],
                length_assessment="Good",
                strengths=["Strong"],
                improvements=["More detail"],
            )  # type: ignore[call-arg]

    def test_requires_keyword_alignment(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetterReview(
                overall_score=85,
                tone_assessment="Good",
                specificity_score=70,
                length_assessment="Good",
                strengths=["Strong"],
                improvements=["More detail"],
            )  # type: ignore[call-arg]

    def test_requires_length_assessment(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetterReview(
                overall_score=85,
                tone_assessment="Good",
                specificity_score=70,
                keyword_alignment=["Python"],
                strengths=["Strong"],
                improvements=["More detail"],
            )  # type: ignore[call-arg]

    def test_requires_strengths(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetterReview(
                overall_score=85,
                tone_assessment="Good",
                specificity_score=70,
                keyword_alignment=["Python"],
                length_assessment="Good",
                improvements=["More detail"],
            )  # type: ignore[call-arg]

    def test_requires_improvements(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetterReview(
                overall_score=85,
                tone_assessment="Good",
                specificity_score=70,
                keyword_alignment=["Python"],
                length_assessment="Good",
                strengths=["Strong"],
            )  # type: ignore[call-arg]


class TestCoverLetterReviewScoreBounds:
    """Tests for score field constraints (0-100)."""

    def test_overall_score_at_lower_bound(self) -> None:
        review = _make_review(overall_score=0)
        assert review.overall_score == 0

    def test_overall_score_at_upper_bound(self) -> None:
        review = _make_review(overall_score=100)
        assert review.overall_score == 100

    def test_overall_score_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_review(overall_score=-1)

    def test_overall_score_above_100_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_review(overall_score=101)

    def test_specificity_score_at_lower_bound(self) -> None:
        review = _make_review(specificity_score=0)
        assert review.specificity_score == 0

    def test_specificity_score_at_upper_bound(self) -> None:
        review = _make_review(specificity_score=100)
        assert review.specificity_score == 100

    def test_specificity_score_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_review(specificity_score=-1)

    def test_specificity_score_above_100_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_review(specificity_score=101)


class TestCoverLetterReviewDefaults:
    """Tests for default values."""

    def test_red_flags_defaults_to_empty_list(self) -> None:
        review = _make_review()
        assert review.red_flags == []


class TestCoverLetterReviewOptionalFields:
    """Tests for optional fields."""

    def test_red_flags_when_provided(self) -> None:
        review = _make_review(red_flags=["Factual error about company founding"])
        assert review.red_flags == ["Factual error about company founding"]


class TestCoverLetterReviewSerialization:
    """Tests for model serialization."""

    def test_model_dump_contains_scores(self) -> None:
        review = _make_review()
        data = review.model_dump()
        assert data["overall_score"] == 85
        assert data["specificity_score"] == 70

    def test_round_trip_from_dict(self) -> None:
        review = _make_review(red_flags=["Error"])
        data = review.model_dump()
        restored = CoverLetterReview(**data)
        assert restored == review
