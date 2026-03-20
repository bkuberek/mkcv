"""Tests for SkillsSection model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.skill_group import SkillGroup
from mkcv.core.models.skills_section import SkillsSection


class TestSkillsSection:
    """Tests for SkillsSection wrapper model."""

    def test_valid_creation(self) -> None:
        groups = [
            SkillGroup(label="Languages", skills=["Python", "Go"]),
            SkillGroup(label="Tools", skills=["Docker", "Kubernetes"]),
        ]
        section = SkillsSection(skills=groups)
        assert len(section.skills) == 2
        assert section.skills[0].label == "Languages"

    def test_empty_skills_list(self) -> None:
        section = SkillsSection(skills=[])
        assert section.skills == []

    def test_single_group(self) -> None:
        group = SkillGroup(label="Frameworks", skills=["FastAPI"])
        section = SkillsSection(skills=[group])
        assert len(section.skills) == 1
        assert section.skills[0].skills == ["FastAPI"]

    def test_skills_required(self) -> None:
        with pytest.raises(ValidationError):
            SkillsSection()  # type: ignore[call-arg]

    def test_model_dump(self) -> None:
        groups = [SkillGroup(label="Languages", skills=["Python", "Go"])]
        section = SkillsSection(skills=groups)
        data = section.model_dump()
        assert data == {
            "skills": [{"label": "Languages", "skills": ["Python", "Go"]}],
        }

    def test_model_validate(self) -> None:
        raw = {
            "skills": [
                {"label": "Languages", "skills": ["Python", "Go"]},
                {"label": "Tools", "skills": ["Docker"]},
            ],
        }
        section = SkillsSection.model_validate(raw)
        assert len(section.skills) == 2
        assert section.skills[1].label == "Tools"

    def test_roundtrip_serialization(self) -> None:
        groups = [SkillGroup(label="Languages", skills=["Python"])]
        section = SkillsSection(skills=groups)
        json_str = section.model_dump_json()
        restored = SkillsSection.model_validate_json(json_str)
        assert restored == section
