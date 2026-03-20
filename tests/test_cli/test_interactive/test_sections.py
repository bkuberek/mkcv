"""Tests for section types and the build_sections builder."""

from mkcv.cli.interactive.sections import (
    SectionInfo,
    SectionKind,
    SectionState,
    build_sections,
)
from mkcv.core.models.mission_statement import MissionStatement
from mkcv.core.models.skill_group import SkillGroup
from mkcv.core.models.tailored_bullet import TailoredBullet
from mkcv.core.models.tailored_content import TailoredContent
from mkcv.core.models.tailored_role import TailoredRole

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_bullet(text: str = "Led cross-functional team") -> TailoredBullet:
    return TailoredBullet(
        original="Original bullet",
        rewritten=text,
        keywords_incorporated=["leadership"],
        confidence="high",
    )


def _make_role(
    company: str = "Acme Corp",
    position: str = "Senior Engineer",
) -> TailoredRole:
    return TailoredRole(
        company=company,
        position=position,
        start_date="2020-01",
        end_date="2023-06",
        bullets=[_make_bullet()],
    )


def _make_mission() -> MissionStatement:
    return MissionStatement(
        text="Experienced engineer passionate about building great products.",
        rationale="Aligns with company mission.",
    )


def _make_skill_group() -> SkillGroup:
    return SkillGroup(label="Languages", skills=["Python", "Go", "TypeScript"])


def _make_full_content() -> TailoredContent:
    return TailoredContent(
        mission=_make_mission(),
        skills=[_make_skill_group()],
        roles=[
            _make_role("Acme Corp", "Senior Engineer"),
            _make_role("Beta Inc", "Staff Engineer"),
        ],
        earlier_experience="Earlier roles in consulting and freelance.",
        languages=["English", "Spanish"],
    )


def _make_minimal_content() -> TailoredContent:
    return TailoredContent(
        mission=_make_mission(),
        skills=[],
        roles=[_make_role()],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildSectionsFullContent:
    """Full TailoredContent produces the correct section list."""

    def test_section_count(self) -> None:
        sections = build_sections(_make_full_content())
        # mission + skills + 2 roles + earlier_experience + languages = 6
        assert len(sections) == 6

    def test_section_order(self) -> None:
        sections = build_sections(_make_full_content())
        kinds = [s.kind for s in sections]
        assert kinds == [
            SectionKind.MISSION,
            SectionKind.SKILLS,
            SectionKind.EXPERIENCE,
            SectionKind.EXPERIENCE,
            SectionKind.EARLIER_EXPERIENCE,
            SectionKind.LANGUAGES,
        ]

    def test_experience_labels_include_company_and_position(self) -> None:
        sections = build_sections(_make_full_content())
        experience_sections = [s for s in sections if s.kind == SectionKind.EXPERIENCE]
        assert "Acme Corp" in experience_sections[0].label
        assert "Senior Engineer" in experience_sections[0].label
        assert "Beta Inc" in experience_sections[1].label
        assert "Staff Engineer" in experience_sections[1].label


class TestBuildSectionsMinimalContent:
    """Minimal content produces only the sections that are present."""

    def test_section_count(self) -> None:
        sections = build_sections(_make_minimal_content())
        # mission + 1 role (no skills, no earlier_experience, no languages)
        assert len(sections) == 2

    def test_section_kinds(self) -> None:
        sections = build_sections(_make_minimal_content())
        kinds = [s.kind for s in sections]
        assert kinds == [SectionKind.MISSION, SectionKind.EXPERIENCE]


class TestBuildSectionsEmptyRoles:
    """Empty roles list produces no EXPERIENCE sections."""

    def test_no_experience_sections(self) -> None:
        content = TailoredContent(
            mission=_make_mission(),
            skills=[_make_skill_group()],
            roles=[],
        )
        sections = build_sections(content)
        experience = [s for s in sections if s.kind == SectionKind.EXPERIENCE]
        assert len(experience) == 0


class TestSectionRoleIndex:
    """role_index is set correctly on all sections."""

    def test_experience_sections_have_sequential_role_index(self) -> None:
        sections = build_sections(_make_full_content())
        experience = [s for s in sections if s.kind == SectionKind.EXPERIENCE]
        indices = [s.role_index for s in experience]
        assert indices == [0, 1]

    def test_non_experience_sections_have_none_role_index(self) -> None:
        sections = build_sections(_make_full_content())
        non_experience = [s for s in sections if s.kind != SectionKind.EXPERIENCE]
        for section in non_experience:
            assert section.role_index is None


class TestSectionInitialState:
    """All sections start with PENDING state."""

    def test_all_sections_start_pending(self) -> None:
        sections = build_sections(_make_full_content())
        for section in sections:
            assert section.state == SectionState.PENDING


class TestSectionInfoDefaults:
    """SectionInfo dataclass defaults are correct."""

    def test_default_state_is_pending(self) -> None:
        info = SectionInfo(kind=SectionKind.MISSION, label="Mission")
        assert info.state == SectionState.PENDING

    def test_default_role_index_is_none(self) -> None:
        info = SectionInfo(kind=SectionKind.MISSION, label="Mission")
        assert info.role_index is None
