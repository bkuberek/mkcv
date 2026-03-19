"""Tests for KeywordCoverage model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.keyword_coverage import KeywordCoverage


class TestKeywordCoverage:
    """Tests for KeywordCoverage model."""

    def test_valid_creation(self) -> None:
        coverage = KeywordCoverage(
            total_keywords=20,
            matched_keywords=15,
            coverage_percent=75.0,
            missing_keywords=["Terraform", "CI/CD"],
            suggestions=["Add Terraform to skills section"],
        )
        assert coverage.total_keywords == 20

    def test_matched_keywords(self) -> None:
        coverage = KeywordCoverage(
            total_keywords=10,
            matched_keywords=8,
            coverage_percent=80.0,
            missing_keywords=["GraphQL", "gRPC"],
            suggestions=[],
        )
        assert coverage.matched_keywords == 8

    def test_full_coverage(self) -> None:
        coverage = KeywordCoverage(
            total_keywords=5,
            matched_keywords=5,
            coverage_percent=100.0,
            missing_keywords=[],
            suggestions=[],
        )
        assert coverage.coverage_percent == 100.0

    def test_zero_coverage(self) -> None:
        coverage = KeywordCoverage(
            total_keywords=10,
            matched_keywords=0,
            coverage_percent=0.0,
            missing_keywords=["Python", "Go", "Rust"],
            suggestions=["Review technical stack"],
        )
        assert coverage.coverage_percent == 0.0

    def test_empty_missing_keywords(self) -> None:
        coverage = KeywordCoverage(
            total_keywords=5,
            matched_keywords=5,
            coverage_percent=100.0,
            missing_keywords=[],
            suggestions=[],
        )
        assert coverage.missing_keywords == []

    def test_total_keywords_required(self) -> None:
        with pytest.raises(ValidationError):
            KeywordCoverage(
                matched_keywords=5,  # type: ignore[call-arg]
                coverage_percent=50.0,
                missing_keywords=[],
                suggestions=[],
            )

    def test_model_dump(self) -> None:
        coverage = KeywordCoverage(
            total_keywords=10,
            matched_keywords=7,
            coverage_percent=70.0,
            missing_keywords=["Docker"],
            suggestions=["Mention Docker experience"],
        )
        data = coverage.model_dump()
        assert data == {
            "total_keywords": 10,
            "matched_keywords": 7,
            "coverage_percent": 70.0,
            "missing_keywords": ["Docker"],
            "suggestions": ["Mention Docker experience"],
        }
