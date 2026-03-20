"""Tests for EarlierExperienceSection model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.earlier_experience_section import EarlierExperienceSection


class TestEarlierExperienceSection:
    """Tests for EarlierExperienceSection wrapper model."""

    def test_valid_creation(self) -> None:
        section = EarlierExperienceSection(
            earlier_experience="10+ years in backend engineering at startups."
        )
        assert section.earlier_experience == (
            "10+ years in backend engineering at startups."
        )

    def test_empty_string(self) -> None:
        section = EarlierExperienceSection(earlier_experience="")
        assert section.earlier_experience == ""

    def test_earlier_experience_required(self) -> None:
        with pytest.raises(ValidationError):
            EarlierExperienceSection()  # type: ignore[call-arg]

    def test_model_dump(self) -> None:
        section = EarlierExperienceSection(
            earlier_experience="Prior roles in data engineering."
        )
        data = section.model_dump()
        assert data == {
            "earlier_experience": "Prior roles in data engineering.",
        }

    def test_model_validate(self) -> None:
        raw = {"earlier_experience": "Led teams at two Fortune 500 companies."}
        section = EarlierExperienceSection.model_validate(raw)
        assert "Fortune 500" in section.earlier_experience

    def test_roundtrip_serialization(self) -> None:
        section = EarlierExperienceSection(
            earlier_experience="Extensive background in ML infrastructure."
        )
        json_str = section.model_dump_json()
        restored = EarlierExperienceSection.model_validate_json(json_str)
        assert restored == section
