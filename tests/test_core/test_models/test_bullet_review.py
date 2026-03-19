"""Tests for BulletReview model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.bullet_review import BulletReview


class TestBulletReview:
    """Tests for BulletReview model."""

    def test_valid_faithful_classification(self) -> None:
        review = BulletReview(
            bullet_text="Led migration of 50+ microservices to Kubernetes",
            classification="faithful",
        )
        assert review.classification == "faithful"

    def test_valid_enhanced_classification(self) -> None:
        review = BulletReview(
            bullet_text="Improved system throughput by 3x",
            classification="enhanced",
        )
        assert review.classification == "enhanced"

    def test_valid_stretched_classification(self) -> None:
        review = BulletReview(
            bullet_text="Architected company-wide data platform",
            classification="stretched",
        )
        assert review.classification == "stretched"

    def test_valid_fabricated_classification(self) -> None:
        review = BulletReview(
            bullet_text="Invented a new algorithm",
            classification="fabricated",
        )
        assert review.classification == "fabricated"

    def test_invalid_classification_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BulletReview(
                bullet_text="Some bullet",
                classification="accurate",  # type: ignore[arg-type]
            )

    def test_explanation_defaults_to_none(self) -> None:
        review = BulletReview(
            bullet_text="Led migration",
            classification="faithful",
        )
        assert review.explanation is None

    def test_explanation_with_value(self) -> None:
        review = BulletReview(
            bullet_text="Led migration",
            classification="enhanced",
            explanation="Metrics were slightly generalized",
        )
        assert review.explanation == "Metrics were slightly generalized"

    def test_suggested_fix_defaults_to_none(self) -> None:
        review = BulletReview(
            bullet_text="Led migration",
            classification="faithful",
        )
        assert review.suggested_fix is None

    def test_suggested_fix_with_value(self) -> None:
        review = BulletReview(
            bullet_text="Invented a new algorithm",
            classification="fabricated",
            suggested_fix="Replace with actual contribution details",
        )
        assert review.suggested_fix == "Replace with actual contribution details"

    def test_bullet_text_required(self) -> None:
        with pytest.raises(ValidationError):
            BulletReview(
                classification="faithful",  # type: ignore[call-arg]
            )

    def test_model_dump(self) -> None:
        review = BulletReview(
            bullet_text="Led migration",
            classification="faithful",
            explanation="Accurate representation",
            suggested_fix=None,
        )
        data = review.model_dump()
        assert data == {
            "bullet_text": "Led migration",
            "classification": "faithful",
            "explanation": "Accurate representation",
            "suggested_fix": None,
        }
