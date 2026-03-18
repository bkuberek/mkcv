"""Tests for the Requirement model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.requirement import Requirement


class TestRequirement:
    """Tests for Requirement model creation and validation."""

    def test_valid_requirement_creation(self) -> None:
        req = Requirement(
            skill="Python",
            importance="must_have",
            context="Backend development",
        )
        assert req.skill == "Python"

    def test_importance_must_have(self) -> None:
        req = Requirement(
            skill="Python",
            importance="must_have",
            context="Backend",
        )
        assert req.importance == "must_have"

    def test_importance_strong_prefer(self) -> None:
        req = Requirement(
            skill="Go",
            importance="strong_prefer",
            context="Systems programming",
        )
        assert req.importance == "strong_prefer"

    def test_importance_nice_to_have(self) -> None:
        req = Requirement(
            skill="Rust",
            importance="nice_to_have",
            context="Optional systems work",
        )
        assert req.importance == "nice_to_have"

    def test_invalid_importance_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Requirement(
                skill="Python",
                importance="required",  # type: ignore[arg-type]
                context="Backend",
            )

    def test_years_implied_defaults_to_none(self) -> None:
        req = Requirement(
            skill="Python",
            importance="must_have",
            context="Backend",
        )
        assert req.years_implied is None

    def test_years_implied_with_value(self) -> None:
        req = Requirement(
            skill="Python",
            importance="must_have",
            years_implied=5,
            context="Backend development",
        )
        assert req.years_implied == 5

    def test_context_is_required(self) -> None:
        with pytest.raises(ValidationError):
            Requirement(
                skill="Python",
                importance="must_have",
                # missing context
            )

    def test_skill_is_required(self) -> None:
        with pytest.raises(ValidationError):
            Requirement(
                importance="must_have",  # type: ignore[call-arg]
                context="Backend",
            )
