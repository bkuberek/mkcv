"""Tests for StageAssignment (design section 3.6)."""

from typing import Any

import pytest
from pydantic import ValidationError

from mkcv.core.models.provider_kind import ProviderKind
from mkcv.core.models.stage_assignment import StageAssignment
from mkcv.core.models.stage_config import StageConfig
from mkcv.core.models.stage_key import StageKey


def _assignment(**overrides: Any) -> StageAssignment:
    fields: dict[str, Any] = {
        "stage": StageKey.TAILOR,
        "provider": "openai",
        "provider_kind": ProviderKind.OPENAI,
        "model": "gpt-6.1-sol",
        "temperature": 0.5,
        "source": "config",
    }
    fields.update(overrides)
    return StageAssignment(**fields)


class TestToStageConfig:
    def test_returns_a_stage_config(self) -> None:
        assert isinstance(_assignment().to_stage_config(), StageConfig)

    def test_carries_provider_model_and_temperature(self) -> None:
        config = _assignment().to_stage_config()
        assert (config.provider, config.model, config.temperature) == (
            "openai",
            "gpt-6.1-sol",
            0.5,
        )

    def test_the_provider_name_is_used_not_the_kind(self) -> None:
        assignment = _assignment(
            provider="groq",
            provider_kind=ProviderKind.OPENAI_COMPATIBLE,
            model="llama-3.3-70b-versatile",
        )
        assert assignment.to_stage_config().provider == "groq"

    @pytest.mark.parametrize("source", ["cli", "config", "profile"])
    def test_the_source_does_not_change_the_config(self, source: str) -> None:
        config = _assignment(source=source).to_stage_config()
        assert config == StageConfig(
            provider="openai", model="gpt-6.1-sol", temperature=0.5
        )

    def test_an_out_of_range_temperature_fails_when_converted(self) -> None:
        with pytest.raises(ValidationError):
            _assignment(temperature=2.5).to_stage_config()


class TestFields:
    @pytest.mark.parametrize("source", ["cli", "config", "profile"])
    def test_known_sources_are_accepted(self, source: str) -> None:
        assert _assignment(source=source).source == source

    @pytest.mark.parametrize("source", ["default", "preset", ""])
    def test_other_sources_are_rejected(self, source: str) -> None:
        with pytest.raises(ValidationError):
            _assignment(source=source)

    def test_provider_kind_accepts_its_string_value(self) -> None:
        assert _assignment(provider_kind="google").provider_kind is ProviderKind.GOOGLE

    def test_stage_accepts_its_string_value(self) -> None:
        assert _assignment(stage="cover_letter.review").stage is (
            StageKey.COVER_LETTER_REVIEW
        )

    def test_unknown_stage_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _assignment(stage="translate")

    def test_every_field_is_required(self) -> None:
        fields = set(StageAssignment.model_fields)
        assert fields == {
            "stage",
            "provider",
            "provider_kind",
            "model",
            "temperature",
            "source",
        }
        for name in fields:
            with pytest.raises(ValidationError):
                StageAssignment.model_validate(
                    {
                        key: value
                        for key, value in _assignment().model_dump().items()
                        if key != name
                    }
                )


class TestImmutability:
    def test_assignments_are_frozen(self) -> None:
        assignment = _assignment()
        with pytest.raises(ValidationError):
            assignment.model = "other"  # type: ignore[misc]

    def test_equal_fields_make_equal_assignments(self) -> None:
        assert _assignment() == _assignment()

    def test_a_changed_source_makes_a_different_assignment(self) -> None:
        assert _assignment(source="cli") != _assignment(source="profile")
