"""Tests for StageConfig model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.stage_config import StageConfig


class TestStageConfig:
    """Tests for StageConfig model."""

    def test_valid_creation(self) -> None:
        config = StageConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            temperature=0.3,
        )
        assert config.provider == "anthropic"

    def test_model_field(self) -> None:
        config = StageConfig(
            provider="openai",
            model="gpt-4o",
            temperature=0.7,
        )
        assert config.model == "gpt-4o"

    def test_temperature_value(self) -> None:
        config = StageConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            temperature=0.5,
        )
        assert config.temperature == 0.5

    def test_temperature_zero_allowed(self) -> None:
        config = StageConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            temperature=0.0,
        )
        assert config.temperature == 0.0

    def test_temperature_two_allowed(self) -> None:
        config = StageConfig(
            provider="openai",
            model="gpt-4o",
            temperature=2.0,
        )
        assert config.temperature == 2.0

    def test_temperature_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StageConfig(
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                temperature=-0.1,
            )

    def test_temperature_above_two_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StageConfig(
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                temperature=2.1,
            )

    def test_provider_required(self) -> None:
        with pytest.raises(ValidationError):
            StageConfig(
                model="claude-sonnet-4-20250514",  # type: ignore[call-arg]
                temperature=0.3,
            )

    def test_model_required(self) -> None:
        with pytest.raises(ValidationError):
            StageConfig(
                provider="anthropic",  # type: ignore[call-arg]
                temperature=0.3,
            )

    def test_temperature_required(self) -> None:
        with pytest.raises(ValidationError):
            StageConfig(
                provider="anthropic",  # type: ignore[call-arg]
                model="claude-sonnet-4-20250514",
            )

    def test_model_dump(self) -> None:
        config = StageConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            temperature=0.3,
        )
        data = config.model_dump()
        assert data == {
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514",
            "temperature": 0.3,
        }
