"""Tests for LanguagesSection model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.languages_section import LanguagesSection


class TestLanguagesSection:
    """Tests for LanguagesSection wrapper model."""

    def test_valid_creation(self) -> None:
        section = LanguagesSection(languages=["English", "Spanish", "French"])
        assert section.languages == ["English", "Spanish", "French"]

    def test_empty_languages_list(self) -> None:
        section = LanguagesSection(languages=[])
        assert section.languages == []

    def test_single_language(self) -> None:
        section = LanguagesSection(languages=["English"])
        assert len(section.languages) == 1

    def test_languages_required(self) -> None:
        with pytest.raises(ValidationError):
            LanguagesSection()  # type: ignore[call-arg]

    def test_model_dump(self) -> None:
        section = LanguagesSection(languages=["English", "Spanish"])
        data = section.model_dump()
        assert data == {"languages": ["English", "Spanish"]}

    def test_model_validate(self) -> None:
        raw = {"languages": ["English", "German", "Mandarin"]}
        section = LanguagesSection.model_validate(raw)
        assert len(section.languages) == 3
        assert section.languages[2] == "Mandarin"

    def test_roundtrip_serialization(self) -> None:
        section = LanguagesSection(languages=["English", "French"])
        json_str = section.model_dump_json()
        restored = LanguagesSection.model_validate_json(json_str)
        assert restored == section
