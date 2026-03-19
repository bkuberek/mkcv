"""Tests for StageMetadata model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.stage_metadata import StageMetadata


class TestStageMetadata:
    """Tests for StageMetadata model."""

    def test_valid_creation(self) -> None:
        meta = StageMetadata(
            stage_number=1,
            stage_name="analyze_jd",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            temperature=0.3,
            input_tokens=2000,
            output_tokens=800,
            cost_usd=0.018,
            duration_seconds=2.5,
        )
        assert meta.stage_name == "analyze_jd"

    def test_retries_defaults_to_zero(self) -> None:
        meta = StageMetadata(
            stage_number=1,
            stage_name="analyze_jd",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            temperature=0.3,
            input_tokens=2000,
            output_tokens=800,
            cost_usd=0.018,
            duration_seconds=2.5,
        )
        assert meta.retries == 0

    def test_retries_with_value(self) -> None:
        meta = StageMetadata(
            stage_number=3,
            stage_name="tailor_content",
            provider="openai",
            model="gpt-4o",
            temperature=0.7,
            input_tokens=3000,
            output_tokens=1500,
            cost_usd=0.025,
            duration_seconds=4.1,
            retries=2,
        )
        assert meta.retries == 2

    def test_stage_number_required(self) -> None:
        with pytest.raises(ValidationError):
            StageMetadata(
                stage_name="analyze_jd",  # type: ignore[call-arg]
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                temperature=0.3,
                input_tokens=2000,
                output_tokens=800,
                cost_usd=0.018,
                duration_seconds=2.5,
            )

    def test_stage_name_required(self) -> None:
        with pytest.raises(ValidationError):
            StageMetadata(
                stage_number=1,  # type: ignore[call-arg]
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                temperature=0.3,
                input_tokens=2000,
                output_tokens=800,
                cost_usd=0.018,
                duration_seconds=2.5,
            )

    def test_model_dump_includes_all_fields(self) -> None:
        meta = StageMetadata(
            stage_number=1,
            stage_name="analyze_jd",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            temperature=0.3,
            input_tokens=2000,
            output_tokens=800,
            cost_usd=0.018,
            duration_seconds=2.5,
        )
        data = meta.model_dump()
        expected_keys = {
            "stage_number",
            "stage_name",
            "provider",
            "model",
            "temperature",
            "input_tokens",
            "output_tokens",
            "cost_usd",
            "duration_seconds",
            "retries",
        }
        assert set(data.keys()) == expected_keys

    def test_zero_cost_allowed(self) -> None:
        meta = StageMetadata(
            stage_number=1,
            stage_name="analyze_jd",
            provider="stub",
            model="stub-model",
            temperature=0.0,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            duration_seconds=0.0,
        )
        assert meta.cost_usd == 0.0
