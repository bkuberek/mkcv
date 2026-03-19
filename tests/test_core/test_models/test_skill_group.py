"""Tests for SkillGroup model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.skill_group import SkillGroup


class TestSkillGroup:
    """Tests for SkillGroup model."""

    def test_valid_creation(self) -> None:
        group = SkillGroup(label="Languages", skills=["Python", "Go", "Rust"])
        assert group.label == "Languages"

    def test_skills_list(self) -> None:
        group = SkillGroup(label="Tools", skills=["Docker", "Kubernetes"])
        assert group.skills == ["Docker", "Kubernetes"]

    def test_empty_skills_allowed(self) -> None:
        group = SkillGroup(label="Empty", skills=[])
        assert group.skills == []

    def test_label_required(self) -> None:
        with pytest.raises(ValidationError):
            SkillGroup(skills=["Python"])  # type: ignore[call-arg]

    def test_skills_required(self) -> None:
        with pytest.raises(ValidationError):
            SkillGroup(label="Languages")  # type: ignore[call-arg]

    def test_model_dump(self) -> None:
        group = SkillGroup(label="Languages", skills=["Python", "Go"])
        data = group.model_dump()
        assert data == {"label": "Languages", "skills": ["Python", "Go"]}
