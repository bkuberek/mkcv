"""Tests for Rich display helpers in interactive review."""

from io import StringIO

from rich.console import Console

from mkcv.cli.interactive.display import (
    render_help,
    render_section,
    render_status_grid,
)
from mkcv.cli.interactive.sections import (
    SectionInfo,
    SectionKind,
    SectionState,
)
from mkcv.core.models.mission_statement import MissionStatement
from mkcv.core.models.skill_group import SkillGroup
from mkcv.core.models.tailored_bullet import TailoredBullet
from mkcv.core.models.tailored_content import TailoredContent
from mkcv.core.models.tailored_role import TailoredRole

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _capture_console() -> tuple[Console, StringIO]:
    """Create a Console that writes to a StringIO buffer."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    return console, buf


def _make_bullet(text: str = "Delivered 3x improvement") -> TailoredBullet:
    return TailoredBullet(
        original="Original bullet",
        rewritten=text,
        keywords_incorporated=["performance"],
        confidence="high",
    )


def _make_role(
    company: str = "Acme Corp",
    position: str = "Senior Engineer",
) -> TailoredRole:
    return TailoredRole(
        company=company,
        position=position,
        location="New York, NY",
        start_date="2020-01",
        end_date="2023-06",
        summary="Led platform engineering team.",
        bullets=[_make_bullet(), _make_bullet("Reduced latency by 40%")],
        tech_stack="Python, Kubernetes, PostgreSQL",
    )


def _make_content() -> TailoredContent:
    return TailoredContent(
        mission=MissionStatement(
            text="Passionate about scalable systems.",
            rationale="Matches job focus.",
        ),
        skills=[
            SkillGroup(label="Languages", skills=["Python", "Go"]),
            SkillGroup(label="Cloud", skills=["AWS", "GCP"]),
        ],
        roles=[_make_role()],
        earlier_experience="Earlier consulting roles.",
        languages=["English", "German"],
    )


# ---------------------------------------------------------------------------
# Tests: render_section
# ---------------------------------------------------------------------------


class TestRenderSectionMission:
    """render_section for MISSION includes mission text."""

    def test_contains_mission_text(self) -> None:
        console, buf = _capture_console()
        content = _make_content()
        section = SectionInfo(kind=SectionKind.MISSION, label="Mission")

        render_section(console, section, content)
        output = buf.getvalue()

        assert "Passionate about scalable systems" in output

    def test_contains_rationale(self) -> None:
        console, buf = _capture_console()
        content = _make_content()
        section = SectionInfo(kind=SectionKind.MISSION, label="Mission")

        render_section(console, section, content)
        output = buf.getvalue()

        assert "Matches job focus" in output


class TestRenderSectionSkills:
    """render_section for SKILLS includes skill group labels and skills."""

    def test_contains_skill_labels(self) -> None:
        console, buf = _capture_console()
        content = _make_content()
        section = SectionInfo(kind=SectionKind.SKILLS, label="Skills")

        render_section(console, section, content)
        output = buf.getvalue()

        assert "Languages" in output
        assert "Cloud" in output

    def test_contains_individual_skills(self) -> None:
        console, buf = _capture_console()
        content = _make_content()
        section = SectionInfo(kind=SectionKind.SKILLS, label="Skills")

        render_section(console, section, content)
        output = buf.getvalue()

        assert "Python" in output
        assert "AWS" in output


class TestRenderSectionExperience:
    """render_section for EXPERIENCE includes company, position, and bullets."""

    def test_contains_company(self) -> None:
        console, buf = _capture_console()
        content = _make_content()
        section = SectionInfo(
            kind=SectionKind.EXPERIENCE,
            label="Experience: Acme Corp",
            role_index=0,
        )

        render_section(console, section, content)
        output = buf.getvalue()

        assert "Acme Corp" in output

    def test_contains_position(self) -> None:
        console, buf = _capture_console()
        content = _make_content()
        section = SectionInfo(
            kind=SectionKind.EXPERIENCE,
            label="Experience: Acme Corp",
            role_index=0,
        )

        render_section(console, section, content)
        output = buf.getvalue()

        assert "Senior Engineer" in output

    def test_contains_bullet_text(self) -> None:
        console, buf = _capture_console()
        content = _make_content()
        section = SectionInfo(
            kind=SectionKind.EXPERIENCE,
            label="Experience: Acme Corp",
            role_index=0,
        )

        render_section(console, section, content)
        output = buf.getvalue()

        assert "Delivered 3x improvement" in output
        assert "Reduced latency by 40%" in output

    def test_contains_tech_stack(self) -> None:
        console, buf = _capture_console()
        content = _make_content()
        section = SectionInfo(
            kind=SectionKind.EXPERIENCE,
            label="Experience: Acme Corp",
            role_index=0,
        )

        render_section(console, section, content)
        output = buf.getvalue()

        assert "Python, Kubernetes, PostgreSQL" in output

    def test_contains_location(self) -> None:
        console, buf = _capture_console()
        content = _make_content()
        section = SectionInfo(
            kind=SectionKind.EXPERIENCE,
            label="Experience: Acme Corp",
            role_index=0,
        )

        render_section(console, section, content)
        output = buf.getvalue()

        assert "New York, NY" in output


class TestRenderSectionEarlierExperience:
    """render_section for EARLIER_EXPERIENCE includes text."""

    def test_contains_earlier_text(self) -> None:
        console, buf = _capture_console()
        content = _make_content()
        section = SectionInfo(
            kind=SectionKind.EARLIER_EXPERIENCE,
            label="Earlier Experience",
        )

        render_section(console, section, content)
        output = buf.getvalue()

        assert "Earlier consulting roles" in output


class TestRenderSectionLanguages:
    """render_section for LANGUAGES includes language names."""

    def test_contains_languages(self) -> None:
        console, buf = _capture_console()
        content = _make_content()
        section = SectionInfo(kind=SectionKind.LANGUAGES, label="Languages")

        render_section(console, section, content)
        output = buf.getvalue()

        assert "English" in output
        assert "German" in output


# ---------------------------------------------------------------------------
# Tests: render_status_grid
# ---------------------------------------------------------------------------


class TestRenderStatusGrid:
    """render_status_grid shows section names and states."""

    def test_shows_section_labels(self) -> None:
        console, buf = _capture_console()
        sections = [
            SectionInfo(kind=SectionKind.MISSION, label="Mission"),
            SectionInfo(
                kind=SectionKind.EXPERIENCE,
                label="Experience: Acme Corp, Senior Engineer",
                role_index=0,
            ),
        ]

        render_status_grid(console, sections, current_index=0)
        output = buf.getvalue()

        assert "Mission" in output
        assert "Acme Corp" in output

    def test_shows_state_labels(self) -> None:
        console, buf = _capture_console()
        sections = [
            SectionInfo(
                kind=SectionKind.MISSION,
                label="Mission",
                state=SectionState.ACCEPTED,
            ),
            SectionInfo(
                kind=SectionKind.SKILLS,
                label="Skills",
                state=SectionState.SKIPPED,
            ),
            SectionInfo(
                kind=SectionKind.EXPERIENCE,
                label="Experience: Acme Corp",
                state=SectionState.PENDING,
                role_index=0,
            ),
        ]

        render_status_grid(console, sections, current_index=2)
        output = buf.getvalue()

        assert "ACCEPTED" in output
        assert "SKIPPED" in output
        assert "PENDING" in output

    def test_shows_section_numbers(self) -> None:
        console, buf = _capture_console()
        sections = [
            SectionInfo(kind=SectionKind.MISSION, label="Mission"),
            SectionInfo(kind=SectionKind.SKILLS, label="Skills"),
        ]

        render_status_grid(console, sections, current_index=0)
        output = buf.getvalue()

        assert "1" in output
        assert "2" in output


# ---------------------------------------------------------------------------
# Tests: render_help
# ---------------------------------------------------------------------------


class TestRenderHelp:
    """render_help lists all commands."""

    def test_lists_all_command_names(self) -> None:
        console, buf = _capture_console()

        render_help(console)
        output = buf.getvalue()

        expected_commands = [
            "/accept",
            "/skip",
            "/edit",
            "/display",
            "/sections",
            "/goto",
            "/done",
            "/cancel",
            "/regenerate",
            "/help",
        ]
        for cmd in expected_commands:
            assert cmd in output

    def test_lists_aliases(self) -> None:
        console, buf = _capture_console()

        render_help(console)
        output = buf.getvalue()

        assert "/a" in output
        assert "/s" in output
        assert "/h" in output
