"""Tests for CoverLetter model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.cover_letter import CoverLetter


def _make_cover_letter(**overrides: object) -> CoverLetter:
    """Build a valid CoverLetter with sensible defaults, applying overrides."""
    defaults: dict[str, object] = {
        "company": "TestCorp",
        "role_title": "Software Engineer",
        "salutation": "Dear Hiring Manager,",
        "opening_paragraph": "I am writing to express my interest.",
        "body_paragraphs": ["First body paragraph.", "Second body paragraph."],
        "closing_paragraph": "I look forward to discussing this opportunity.",
        "candidate_name": "Jane Doe",
    }
    defaults.update(overrides)
    return CoverLetter(**defaults)  # type: ignore[arg-type]


class TestCoverLetterRequiredFields:
    """Tests for required field validation."""

    def test_requires_company(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetter(
                role_title="SWE",
                salutation="Dear,",
                opening_paragraph="Hello",
                body_paragraphs=["Body"],
                closing_paragraph="Thanks",
                candidate_name="Jane",
            )  # type: ignore[call-arg]

    def test_requires_role_title(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetter(
                company="TestCorp",
                salutation="Dear,",
                opening_paragraph="Hello",
                body_paragraphs=["Body"],
                closing_paragraph="Thanks",
                candidate_name="Jane",
            )  # type: ignore[call-arg]

    def test_requires_salutation(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetter(
                company="TestCorp",
                role_title="SWE",
                opening_paragraph="Hello",
                body_paragraphs=["Body"],
                closing_paragraph="Thanks",
                candidate_name="Jane",
            )  # type: ignore[call-arg]

    def test_requires_opening_paragraph(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetter(
                company="TestCorp",
                role_title="SWE",
                salutation="Dear,",
                body_paragraphs=["Body"],
                closing_paragraph="Thanks",
                candidate_name="Jane",
            )  # type: ignore[call-arg]

    def test_requires_body_paragraphs(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetter(
                company="TestCorp",
                role_title="SWE",
                salutation="Dear,",
                opening_paragraph="Hello",
                closing_paragraph="Thanks",
                candidate_name="Jane",
            )  # type: ignore[call-arg]

    def test_requires_closing_paragraph(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetter(
                company="TestCorp",
                role_title="SWE",
                salutation="Dear,",
                opening_paragraph="Hello",
                body_paragraphs=["Body"],
                candidate_name="Jane",
            )  # type: ignore[call-arg]

    def test_requires_candidate_name(self) -> None:
        with pytest.raises(ValidationError):
            CoverLetter(
                company="TestCorp",
                role_title="SWE",
                salutation="Dear,",
                opening_paragraph="Hello",
                body_paragraphs=["Body"],
                closing_paragraph="Thanks",
            )  # type: ignore[call-arg]


class TestCoverLetterDefaults:
    """Tests for default values."""

    def test_sign_off_defaults_to_sincerely(self) -> None:
        cl = _make_cover_letter()
        assert cl.sign_off == "Sincerely,"

    def test_tone_notes_defaults_to_none(self) -> None:
        cl = _make_cover_letter()
        assert cl.tone_notes is None


class TestCoverLetterOptionalFields:
    """Tests for optional fields."""

    def test_custom_sign_off(self) -> None:
        cl = _make_cover_letter(sign_off="Best regards,")
        assert cl.sign_off == "Best regards,"

    def test_tone_notes_when_provided(self) -> None:
        cl = _make_cover_letter(tone_notes="Professional yet approachable")
        assert cl.tone_notes == "Professional yet approachable"


class TestCoverLetterSerialization:
    """Tests for model serialization."""

    def test_model_dump_contains_all_fields(self) -> None:
        cl = _make_cover_letter()
        data = cl.model_dump()
        assert data["company"] == "TestCorp"
        assert data["role_title"] == "Software Engineer"
        assert data["salutation"] == "Dear Hiring Manager,"
        assert data["candidate_name"] == "Jane Doe"

    def test_model_dump_includes_body_paragraphs(self) -> None:
        cl = _make_cover_letter()
        data = cl.model_dump()
        assert len(data["body_paragraphs"]) == 2

    def test_round_trip_from_dict(self) -> None:
        cl = _make_cover_letter(tone_notes="Warm tone")
        data = cl.model_dump()
        restored = CoverLetter(**data)
        assert restored == cl
