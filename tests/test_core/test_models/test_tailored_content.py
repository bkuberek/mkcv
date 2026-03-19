"""Tests for TailoredContent model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.mission_statement import MissionStatement
from mkcv.core.models.skill_group import SkillGroup
from mkcv.core.models.tailored_bullet import TailoredBullet
from mkcv.core.models.tailored_content import TailoredContent
from mkcv.core.models.tailored_role import TailoredRole


def _make_mission() -> MissionStatement:
    return MissionStatement(
        text="Experienced platform engineer",
        rationale="Aligns with JD requirements",
    )


def _make_skill_group() -> SkillGroup:
    return SkillGroup(label="Languages", skills=["Python", "Go"])


def _make_role() -> TailoredRole:
    bullet = TailoredBullet(
        original="Built platform",
        rewritten="Engineered scalable platform",
        keywords_incorporated=["scalable"],
        confidence="high",
    )
    return TailoredRole(
        company="Acme Corp",
        position="Staff Engineer",
        start_date="2020-01",
        end_date="2024-06",
        bullets=[bullet],
    )


class TestTailoredContent:
    """Tests for TailoredContent model."""

    def test_valid_creation(self) -> None:
        content = TailoredContent(
            mission=_make_mission(),
            skills=[_make_skill_group()],
            roles=[_make_role()],
        )
        assert content.mission.text == "Experienced platform engineer"

    def test_skills_list(self) -> None:
        groups = [
            SkillGroup(label="Languages", skills=["Python"]),
            SkillGroup(label="Tools", skills=["Docker", "K8s"]),
        ]
        content = TailoredContent(
            mission=_make_mission(),
            skills=groups,
            roles=[_make_role()],
        )
        assert len(content.skills) == 2

    def test_roles_list(self) -> None:
        content = TailoredContent(
            mission=_make_mission(),
            skills=[],
            roles=[_make_role()],
        )
        assert len(content.roles) == 1

    def test_earlier_experience_defaults_to_none(self) -> None:
        content = TailoredContent(
            mission=_make_mission(),
            skills=[],
            roles=[_make_role()],
        )
        assert content.earlier_experience is None

    def test_earlier_experience_with_value(self) -> None:
        content = TailoredContent(
            mission=_make_mission(),
            skills=[],
            roles=[_make_role()],
            earlier_experience="Previous roles in finance and consulting",
        )
        assert content.earlier_experience == (
            "Previous roles in finance and consulting"
        )

    def test_languages_defaults_to_none(self) -> None:
        content = TailoredContent(
            mission=_make_mission(),
            skills=[],
            roles=[_make_role()],
        )
        assert content.languages is None

    def test_languages_with_value(self) -> None:
        content = TailoredContent(
            mission=_make_mission(),
            skills=[],
            roles=[_make_role()],
            languages=["English", "Spanish", "German"],
        )
        assert content.languages == ["English", "Spanish", "German"]

    def test_low_confidence_flags_defaults_to_empty(self) -> None:
        content = TailoredContent(
            mission=_make_mission(),
            skills=[],
            roles=[_make_role()],
        )
        assert content.low_confidence_flags == []

    def test_low_confidence_flags_with_values(self) -> None:
        flags = ["Bullet about ML may be stretched", "Years at Acme unclear"]
        content = TailoredContent(
            mission=_make_mission(),
            skills=[],
            roles=[_make_role()],
            low_confidence_flags=flags,
        )
        assert content.low_confidence_flags == flags

    def test_mission_required(self) -> None:
        with pytest.raises(ValidationError):
            TailoredContent(
                skills=[],  # type: ignore[call-arg]
                roles=[_make_role()],
            )

    def test_roles_required(self) -> None:
        with pytest.raises(ValidationError):
            TailoredContent(
                mission=_make_mission(),  # type: ignore[call-arg]
                skills=[],
            )

    def test_model_dump_includes_all_fields(self) -> None:
        content = TailoredContent(
            mission=_make_mission(),
            skills=[],
            roles=[_make_role()],
        )
        data = content.model_dump()
        expected_keys = {
            "mission",
            "skills",
            "roles",
            "earlier_experience",
            "languages",
            "low_confidence_flags",
        }
        assert set(data.keys()) == expected_keys
