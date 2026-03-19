"""Tests for CoverLetterResult model."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from mkcv.core.models.cover_letter_result import CoverLetterResult
from mkcv.core.models.stage_metadata import StageMetadata


def _make_stage_metadata(**overrides: object) -> StageMetadata:
    """Build a valid StageMetadata with sensible defaults."""
    defaults: dict[str, object] = {
        "stage_number": 1,
        "stage_name": "generate_cover_letter",
        "provider": "default",
        "model": "claude-sonnet-4-20250514",
        "temperature": 0.6,
        "input_tokens": 100,
        "output_tokens": 200,
        "cost_usd": 0.005,
        "duration_seconds": 1.5,
    }
    defaults.update(overrides)
    return StageMetadata(**defaults)  # type: ignore[arg-type]


def _make_result(**overrides: object) -> CoverLetterResult:
    """Build a valid CoverLetterResult with sensible defaults."""
    defaults: dict[str, object] = {
        "run_id": "abc123def456",
        "timestamp": datetime.now(tz=UTC),
        "company": "TestCorp",
        "role_title": "Software Engineer",
        "stages": [_make_stage_metadata()],
        "total_cost_usd": 0.005,
        "total_duration_seconds": 2.0,
        "review_score": 85,
        "output_paths": {"cover_letter_txt": "/tmp/cover_letter.txt"},
    }
    defaults.update(overrides)
    return CoverLetterResult(**defaults)  # type: ignore[arg-type]


class TestCoverLetterResultRequiredFields:
    """Tests for required field validation."""

    def test_requires_run_id(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetterResult(
                timestamp=datetime.now(tz=UTC),
                company="TestCorp",
                role_title="SWE",
                stages=[],
                total_cost_usd=0.0,
                total_duration_seconds=0.0,
                review_score=0,
                output_paths={},
            )  # type: ignore[call-arg]

    def test_requires_timestamp(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetterResult(
                run_id="abc",
                company="TestCorp",
                role_title="SWE",
                stages=[],
                total_cost_usd=0.0,
                total_duration_seconds=0.0,
                review_score=0,
                output_paths={},
            )  # type: ignore[call-arg]

    def test_requires_company(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetterResult(
                run_id="abc",
                timestamp=datetime.now(tz=UTC),
                role_title="SWE",
                stages=[],
                total_cost_usd=0.0,
                total_duration_seconds=0.0,
                review_score=0,
                output_paths={},
            )  # type: ignore[call-arg]

    def test_requires_review_score(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetterResult(
                run_id="abc",
                timestamp=datetime.now(tz=UTC),
                company="TestCorp",
                role_title="SWE",
                stages=[],
                total_cost_usd=0.0,
                total_duration_seconds=0.0,
                output_paths={},
            )  # type: ignore[call-arg]


class TestCoverLetterResultValues:
    """Tests for field value storage."""

    def test_stores_run_id(self) -> None:
        result = _make_result()
        assert result.run_id == "abc123def456"

    def test_stores_company(self) -> None:
        result = _make_result()
        assert result.company == "TestCorp"

    def test_stores_role_title(self) -> None:
        result = _make_result()
        assert result.role_title == "Software Engineer"

    def test_stores_review_score(self) -> None:
        result = _make_result()
        assert result.review_score == 85

    def test_stores_total_cost(self) -> None:
        result = _make_result()
        assert result.total_cost_usd == 0.005

    def test_stores_stages(self) -> None:
        result = _make_result()
        assert len(result.stages) == 1

    def test_stores_output_paths(self) -> None:
        result = _make_result()
        assert "cover_letter_txt" in result.output_paths


class TestCoverLetterResultSerialization:
    """Tests for model serialization."""

    def test_model_dump_contains_all_fields(self) -> None:
        result = _make_result()
        data = result.model_dump()
        assert "run_id" in data
        assert "timestamp" in data
        assert "company" in data
        assert "review_score" in data
        assert "output_paths" in data

    def test_round_trip_from_dict(self) -> None:
        result = _make_result()
        data = result.model_dump()
        restored = CoverLetterResult(**data)
        assert restored == result
