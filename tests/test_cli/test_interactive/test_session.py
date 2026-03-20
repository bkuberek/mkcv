"""Tests for the interactive REPL session."""

from unittest.mock import patch

from rich.console import Console

from mkcv.cli.interactive.sections import SectionState
from mkcv.cli.interactive.session import InteractiveSession
from mkcv.core.models.mission_statement import MissionStatement
from mkcv.core.models.skill_group import SkillGroup
from mkcv.core.models.tailored_bullet import TailoredBullet
from mkcv.core.models.tailored_content import TailoredContent
from mkcv.core.models.tailored_role import TailoredRole

_PROMPT_ASK = "rich.prompt.Prompt.ask"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_bullet() -> TailoredBullet:
    return TailoredBullet(
        original="Original bullet",
        rewritten="Rewrote bullet for target role",
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
        text="Experienced engineer passionate about building.",
        rationale="Aligns with company mission.",
    )


def _make_content(
    *,
    roles: int = 1,
    with_skills: bool = True,
    with_earlier: bool = False,
    with_languages: bool = False,
) -> TailoredContent:
    role_list = [_make_role(f"Company{i}", f"Role{i}") for i in range(roles)]
    return TailoredContent(
        mission=_make_mission(),
        skills=(
            [SkillGroup(label="Languages", skills=["Python"])] if with_skills else []
        ),
        roles=role_list,
        earlier_experience="Earlier roles" if with_earlier else None,
        languages=["English"] if with_languages else None,
    )


def _quiet_console() -> Console:
    """Console that discards output for quiet test runs."""
    return Console(force_terminal=False, no_color=True, quiet=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAccept:
    """Accepting a section changes its state and advances."""

    def test_accept_changes_state_to_accepted(self) -> None:
        content = _make_content(roles=0, with_skills=False)
        # Only mission section
        session = InteractiveSession(content, _quiet_console())

        with patch(_PROMPT_ASK, side_effect=["/accept", "y"]):
            result = session.run()

        assert result is not None
        assert session._sections[0].state == SectionState.ACCEPTED

    def test_accept_advances_to_next_section(self) -> None:
        content = _make_content(roles=1, with_skills=False)
        # mission + 1 role = 2 sections
        session = InteractiveSession(content, _quiet_console())

        with patch(_PROMPT_ASK, side_effect=["/accept", "/accept", "y"]):
            session.run()

        assert session._sections[0].state == SectionState.ACCEPTED
        assert session._sections[1].state == SectionState.ACCEPTED


class TestSkip:
    """Skipping a section changes its state and advances."""

    def test_skip_changes_state_to_skipped(self) -> None:
        content = _make_content(roles=0, with_skills=False)
        session = InteractiveSession(content, _quiet_console())

        with patch(_PROMPT_ASK, side_effect=["/skip", "y"]):
            session.run()

        assert session._sections[0].state == SectionState.SKIPPED

    def test_skip_advances_to_next_section(self) -> None:
        content = _make_content(roles=1, with_skills=False)
        session = InteractiveSession(content, _quiet_console())

        with patch(_PROMPT_ASK, side_effect=["/skip", "/accept", "y"]):
            session.run()

        assert session._sections[0].state == SectionState.SKIPPED
        assert session._sections[1].state == SectionState.ACCEPTED


class TestDone:
    """The /done command validates that no sections are PENDING."""

    def test_done_with_pending_sections_stays_in_repl(self) -> None:
        content = _make_content(roles=1, with_skills=False)
        # 2 sections: mission + role
        session = InteractiveSession(content, _quiet_console())

        # /done with pending -> error -> /accept both -> auto-finish confirms
        with patch(
            _PROMPT_ASK,
            side_effect=["/done", "/accept", "/accept", "y"],
        ):
            result = session.run()

        assert result is not None

    def test_done_with_all_resolved_returns_content(self) -> None:
        content = _make_content(roles=0, with_skills=False)
        session = InteractiveSession(content, _quiet_console())

        with patch(_PROMPT_ASK, side_effect=["/accept", "y"]):
            result = session.run()

        assert result is not None
        assert isinstance(result, TailoredContent)

    def test_done_decline_confirmation_stays_in_repl(self) -> None:
        content = _make_content(roles=0, with_skills=False)
        session = InteractiveSession(content, _quiet_console())

        # Accept -> auto-done asks confirm -> "n" -> stays in repl
        # Index resets to 0 -> re-renders section -> user types /done -> confirm "y"
        with patch(
            _PROMPT_ASK,
            side_effect=["/accept", "n", "/done", "y"],
        ):
            result = session.run()

        assert result is not None


class TestCancel:
    """/cancel returns None."""

    def test_cancel_returns_none(self) -> None:
        content = _make_content(roles=0, with_skills=False)
        session = InteractiveSession(content, _quiet_console())

        with patch(_PROMPT_ASK, side_effect=["/cancel"]):
            result = session.run()

        assert result is None


class TestKeyboardInterrupt:
    """Ctrl+C (KeyboardInterrupt) returns None."""

    def test_keyboard_interrupt_returns_none(self) -> None:
        content = _make_content(roles=0, with_skills=False)
        session = InteractiveSession(content, _quiet_console())

        with patch(_PROMPT_ASK, side_effect=KeyboardInterrupt):
            result = session.run()

        assert result is None


class TestGoto:
    """/goto navigates to the specified section."""

    def test_goto_navigates_to_section(self) -> None:
        content = _make_content(roles=2, with_skills=True)
        # mission + skills + 2 roles = 4 sections
        session = InteractiveSession(content, _quiet_console())

        # Start at section 1, goto 3, accept role0, then accept remaining
        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/goto 3",  # jump to section 3 (role 0)
                "/accept",  # accept role 0
                "/goto 1",  # back to section 1 (mission)
                "/accept",  # accept mission
                "/goto 2",  # go to section 2 (skills)
                "/accept",  # accept skills
                "/accept",  # accept role 1 (next pending)
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert session._sections[2].state == SectionState.ACCEPTED

    def test_goto_invalid_number_shows_error(self) -> None:
        content = _make_content(roles=0, with_skills=False)
        session = InteractiveSession(content, _quiet_console())

        with patch(_PROMPT_ASK, side_effect=["/goto abc", "/accept", "y"]):
            result = session.run()

        assert result is not None

    def test_goto_out_of_range_shows_error(self) -> None:
        content = _make_content(roles=0, with_skills=False)
        # Only 1 section (mission)
        session = InteractiveSession(content, _quiet_console())

        with patch(_PROMPT_ASK, side_effect=["/goto 5", "/accept", "y"]):
            result = session.run()

        assert result is not None

    def test_goto_zero_shows_error(self) -> None:
        content = _make_content(roles=1, with_skills=False)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=["/goto 0", "/accept", "/accept", "y"],
        ):
            result = session.run()

        assert result is not None


class TestSections:
    """/sections command does not crash."""

    def test_sections_does_not_crash(self) -> None:
        content = _make_content(roles=1, with_skills=True)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=["/sections", "/accept", "/accept", "/accept", "y"],
        ):
            result = session.run()

        assert result is not None


class TestHelp:
    """/help command does not crash."""

    def test_help_does_not_crash(self) -> None:
        content = _make_content(roles=0, with_skills=False)
        session = InteractiveSession(content, _quiet_console())

        with patch(_PROMPT_ASK, side_effect=["/help", "/accept", "y"]):
            result = session.run()

        assert result is not None


class TestRegenerate:
    """/regenerate shows a stub message."""

    def test_regenerate_shows_stub(self) -> None:
        content = _make_content(roles=0, with_skills=False)
        console = _quiet_console()
        session = InteractiveSession(content, console)

        with patch(_PROMPT_ASK, side_effect=["/regenerate", "/accept", "y"]):
            result = session.run()

        assert result is not None


class TestFinalContentExcludesSkipped:
    """_build_final_content removes skipped sections."""

    def test_skipped_role_is_removed(self) -> None:
        content = _make_content(roles=2, with_skills=False)
        # mission + 2 roles
        session = InteractiveSession(content, _quiet_console())

        # Accept mission, skip role0, accept role1
        with patch(
            _PROMPT_ASK,
            side_effect=["/accept", "/skip", "/accept", "y"],
        ):
            result = session.run()

        assert result is not None
        assert len(result.roles) == 1
        assert result.roles[0].company == "Company1"

    def test_skipped_skills_produces_empty_list(self) -> None:
        content = _make_content(roles=0, with_skills=True)
        # mission + skills
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=["/accept", "/skip", "y"],
        ):
            result = session.run()

        assert result is not None
        assert result.skills == []

    def test_skipped_earlier_experience_set_to_none(self) -> None:
        content = _make_content(roles=0, with_skills=False, with_earlier=True)
        # mission + earlier_experience
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=["/accept", "/skip", "y"],
        ):
            result = session.run()

        assert result is not None
        assert result.earlier_experience is None

    def test_skipped_languages_set_to_none(self) -> None:
        content = _make_content(roles=0, with_skills=False, with_languages=True)
        # mission + languages
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=["/accept", "/skip", "y"],
        ):
            result = session.run()

        assert result is not None
        assert result.languages is None

    def test_all_accepted_preserves_content(self) -> None:
        content = _make_content(
            roles=1,
            with_skills=True,
            with_earlier=True,
            with_languages=True,
        )
        session = InteractiveSession(content, _quiet_console())

        # Accept all 5 sections
        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",
                "/accept",
                "/accept",
                "/accept",
                "/accept",
                "y",
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.roles) == 1
        assert len(result.skills) == 1
        assert result.earlier_experience is not None
        assert result.languages is not None


class TestUnknownCommand:
    """Unknown commands do not crash and continue the REPL."""

    def test_unknown_command_continues_repl(self) -> None:
        content = _make_content(roles=0, with_skills=False)
        session = InteractiveSession(content, _quiet_console())

        with patch(_PROMPT_ASK, side_effect=["/foo", "/accept", "y"]):
            result = session.run()

        assert result is not None

    def test_bare_text_is_treated_as_unknown(self) -> None:
        content = _make_content(roles=0, with_skills=False)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=["some text", "/accept", "y"],
        ):
            result = session.run()

        assert result is not None


class TestEditMission:
    """/edit on a mission section updates the mission text."""

    def test_edit_mission_with_inline_text(self) -> None:
        content = _make_content(roles=0, with_skills=False)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=["/edit Updated mission text", "/accept", "y"],
        ):
            result = session.run()

        assert result is not None
        assert result.mission.text == "Updated mission text"

    def test_edit_mission_with_prompt(self) -> None:
        content = _make_content(roles=0, with_skills=False)
        session = InteractiveSession(content, _quiet_console())

        # /edit with no args -> prompts for text
        with patch(
            _PROMPT_ASK,
            side_effect=["/edit", "New prompted text", "/accept", "y"],
        ):
            result = session.run()

        assert result is not None
        assert result.mission.text == "New prompted text"
