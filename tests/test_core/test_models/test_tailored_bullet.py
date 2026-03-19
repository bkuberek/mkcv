"""Tests for TailoredBullet model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.tailored_bullet import TailoredBullet


class TestTailoredBullet:
    """Tests for TailoredBullet model."""

    def test_valid_creation(self) -> None:
        bullet = TailoredBullet(
            original="Built internal deployment tool",
            rewritten="Engineered CI/CD pipeline reducing deploy time by 60%",
            keywords_incorporated=["CI/CD", "pipeline"],
            confidence="high",
        )
        assert bullet.original == "Built internal deployment tool"

    def test_rewritten_field(self) -> None:
        bullet = TailoredBullet(
            original="Worked on database",
            rewritten="Optimized PostgreSQL queries reducing p99 latency by 40%",
            keywords_incorporated=["PostgreSQL"],
            confidence="medium",
        )
        assert bullet.rewritten.startswith("Optimized")

    def test_confidence_high(self) -> None:
        bullet = TailoredBullet(
            original="Led team",
            rewritten="Led cross-functional team of 8 engineers",
            keywords_incorporated=[],
            confidence="high",
        )
        assert bullet.confidence == "high"

    def test_confidence_medium(self) -> None:
        bullet = TailoredBullet(
            original="Helped with project",
            rewritten="Drove project delivery across 3 teams",
            keywords_incorporated=["cross-functional"],
            confidence="medium",
        )
        assert bullet.confidence == "medium"

    def test_confidence_low(self) -> None:
        bullet = TailoredBullet(
            original="Did some coding",
            rewritten="Architected microservices platform serving 1M daily users",
            keywords_incorporated=["microservices", "platform"],
            confidence="low",
        )
        assert bullet.confidence == "low"

    def test_invalid_confidence_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TailoredBullet(
                original="Did work",
                rewritten="Did better work",
                keywords_incorporated=[],
                confidence="very_high",  # type: ignore[arg-type]
            )

    def test_empty_keywords_allowed(self) -> None:
        bullet = TailoredBullet(
            original="Led team",
            rewritten="Led engineering team",
            keywords_incorporated=[],
            confidence="high",
        )
        assert bullet.keywords_incorporated == []

    def test_original_required(self) -> None:
        with pytest.raises(ValidationError):
            TailoredBullet(
                rewritten="Some text",  # type: ignore[call-arg]
                keywords_incorporated=[],
                confidence="high",
            )

    def test_rewritten_required(self) -> None:
        with pytest.raises(ValidationError):
            TailoredBullet(
                original="Some text",  # type: ignore[call-arg]
                keywords_incorporated=[],
                confidence="high",
            )

    def test_model_dump(self) -> None:
        bullet = TailoredBullet(
            original="Built tool",
            rewritten="Engineered deployment automation",
            keywords_incorporated=["automation"],
            confidence="high",
        )
        data = bullet.model_dump()
        assert data == {
            "original": "Built tool",
            "rewritten": "Engineered deployment automation",
            "keywords_incorporated": ["automation"],
            "confidence": "high",
        }
