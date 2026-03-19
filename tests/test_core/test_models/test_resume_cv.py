"""Tests for ResumeCV model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.resume_cv import ResumeCV
from mkcv.core.models.social_network import SocialNetwork


class TestResumeCV:
    """Tests for ResumeCV model."""

    def test_valid_creation(self) -> None:
        cv = ResumeCV(
            name="John Doe",
            location="San Francisco, CA",
            email="john@example.com",
            phone="+1-555-0123",
            summary="Experienced engineer",
            sections={"experience": [{"company": "Acme"}]},
        )
        assert cv.name == "John Doe"

    def test_location_field(self) -> None:
        cv = ResumeCV(
            name="Jane Smith",
            location="Berlin, Germany",
            email="jane@example.com",
            phone="+49-123-456",
            summary="ML engineer",
            sections={},
        )
        assert cv.location == "Berlin, Germany"

    def test_website_defaults_to_none(self) -> None:
        cv = ResumeCV(
            name="John Doe",
            location="NYC",
            email="john@example.com",
            phone="+1-555-0123",
            summary="Engineer",
            sections={},
        )
        assert cv.website is None

    def test_website_with_value(self) -> None:
        cv = ResumeCV(
            name="John Doe",
            location="NYC",
            email="john@example.com",
            phone="+1-555-0123",
            website="https://johndoe.dev",
            summary="Engineer",
            sections={},
        )
        assert cv.website == "https://johndoe.dev"

    def test_social_networks_defaults_to_empty(self) -> None:
        cv = ResumeCV(
            name="John Doe",
            location="NYC",
            email="john@example.com",
            phone="+1-555-0123",
            summary="Engineer",
            sections={},
        )
        assert cv.social_networks == []

    def test_social_networks_with_values(self) -> None:
        networks = [
            SocialNetwork(network="LinkedIn", username="johndoe"),
            SocialNetwork(network="GitHub", username="jdoe"),
        ]
        cv = ResumeCV(
            name="John Doe",
            location="NYC",
            email="john@example.com",
            phone="+1-555-0123",
            social_networks=networks,
            summary="Engineer",
            sections={},
        )
        assert len(cv.social_networks) == 2

    def test_summary_max_length_at_boundary(self) -> None:
        cv = ResumeCV(
            name="John Doe",
            location="NYC",
            email="john@example.com",
            phone="+1-555-0123",
            summary="x" * 300,
            sections={},
        )
        assert len(cv.summary) == 300

    def test_summary_exceeds_max_length_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ResumeCV(
                name="John Doe",
                location="NYC",
                email="john@example.com",
                phone="+1-555-0123",
                summary="x" * 301,
                sections={},
            )

    def test_name_required(self) -> None:
        with pytest.raises(ValidationError):
            ResumeCV(
                location="NYC",  # type: ignore[call-arg]
                email="john@example.com",
                phone="+1-555-0123",
                summary="Engineer",
                sections={},
            )

    def test_sections_required(self) -> None:
        with pytest.raises(ValidationError):
            ResumeCV(
                name="John Doe",  # type: ignore[call-arg]
                location="NYC",
                email="john@example.com",
                phone="+1-555-0123",
                summary="Engineer",
            )

    def test_empty_sections_allowed(self) -> None:
        cv = ResumeCV(
            name="John Doe",
            location="NYC",
            email="john@example.com",
            phone="+1-555-0123",
            summary="Engineer",
            sections={},
        )
        assert cv.sections == {}

    def test_model_dump_includes_all_fields(self) -> None:
        cv = ResumeCV(
            name="John Doe",
            location="NYC",
            email="john@example.com",
            phone="+1-555-0123",
            summary="Engineer",
            sections={},
        )
        data = cv.model_dump()
        expected_keys = {
            "name",
            "location",
            "email",
            "phone",
            "website",
            "social_networks",
            "summary",
            "sections",
        }
        assert set(data.keys()) == expected_keys
