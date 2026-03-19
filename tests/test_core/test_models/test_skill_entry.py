"""Tests for SkillEntry model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.skill_entry import SkillEntry


class TestSkillEntry:
    """Tests for SkillEntry model."""

    def test_valid_creation(self) -> None:
        entry = SkillEntry(label="Languages", details="Python, Go, Rust")
        assert entry.label == "Languages"

    def test_details_field(self) -> None:
        entry = SkillEntry(label="Databases", details="PostgreSQL, Redis, MongoDB")
        assert entry.details == "PostgreSQL, Redis, MongoDB"

    def test_label_required(self) -> None:
        with pytest.raises(ValidationError):
            SkillEntry(details="Python, Go")  # type: ignore[call-arg]

    def test_details_required(self) -> None:
        with pytest.raises(ValidationError):
            SkillEntry(label="Languages")  # type: ignore[call-arg]

    def test_empty_label_allowed(self) -> None:
        entry = SkillEntry(label="", details="Python")
        assert entry.label == ""

    def test_empty_details_allowed(self) -> None:
        entry = SkillEntry(label="Languages", details="")
        assert entry.details == ""

    def test_model_dump(self) -> None:
        entry = SkillEntry(label="Tools", details="Docker, K8s")
        data = entry.model_dump()
        assert data == {"label": "Tools", "details": "Docker, K8s"}
