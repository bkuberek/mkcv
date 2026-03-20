"""Tests for the interactive REPL session."""

from unittest.mock import AsyncMock, MagicMock, patch

from rich.console import Console

from mkcv.cli.interactive.sections import SectionState
from mkcv.cli.interactive.session import InteractiveSession
from mkcv.core.exceptions.pipeline_stage import PipelineStageError
from mkcv.core.models.mission_statement import MissionStatement
from mkcv.core.models.regeneration_context import RegenerationContext
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
    """/regenerate without a regen service shows hint or not-available message."""

    def test_regenerate_without_service_shows_not_available(self) -> None:
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


class TestEditEarlierExperience:
    """/edit on an earlier experience section updates the text."""

    def test_edit_earlier_experience_with_inline_text(self) -> None:
        content = _make_content(roles=0, with_skills=False, with_earlier=True)
        # mission + earlier_experience = 2 sections
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit Updated earlier experience",  # edit earlier experience inline
                "/accept",  # accept earlier experience
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert result.earlier_experience == "Updated earlier experience"

    def test_edit_earlier_experience_with_prompt(self) -> None:
        content = _make_content(roles=0, with_skills=False, with_earlier=True)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit with no args -> prompts
                "New earlier text from prompt",  # user types new text
                "/accept",  # accept earlier experience
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert result.earlier_experience == "New earlier text from prompt"

    def test_edit_earlier_experience_empty_input_unchanged(self) -> None:
        content = _make_content(roles=0, with_skills=False, with_earlier=True)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit with no args -> prompts
                "  ",  # empty/whitespace input -> cancel
                "/accept",  # accept earlier experience unchanged
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert result.earlier_experience == "Earlier roles"  # original value


class TestEditSkills:
    """/edit on a skills section allows editing skill groups."""

    def _make_skills_content(
        self,
        groups: list[SkillGroup] | None = None,
    ) -> TailoredContent:
        """Helper that builds content with specific skill groups."""
        if groups is None:
            groups = [
                SkillGroup(label="Languages", skills=["Python", "Go"]),
                SkillGroup(label="Cloud", skills=["AWS"]),
            ]
        return TailoredContent(
            mission=_make_mission(),
            skills=groups,
            roles=[],
        )

    def test_edit_skill_group_label(self) -> None:
        """Selecting a group and providing a new label updates it."""
        content = self._make_skills_content()
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/goto 2",  # navigate to skills section
                "/edit",  # edit skills
                "1",  # select group 1 (Languages)
                "Programming Languages",  # new label
                "",  # keep existing skills
                "/accept",  # accept skills
                "/goto 1",  # back to mission
                "/accept",  # accept mission
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert result.skills[0].label == "Programming Languages"
        assert result.skills[0].skills == ["Python", "Go"]

    def test_edit_skill_group_skills_list(self) -> None:
        """Selecting a group and providing new skills updates the list."""
        content = self._make_skills_content()
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/goto 2",  # navigate to skills section
                "/edit",  # edit skills
                "1",  # select group 1 (Languages)
                "",  # keep existing label
                "Python, Go, Rust",  # new skills list
                "/accept",  # accept skills
                "/goto 1",  # back to mission
                "/accept",  # accept mission
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert result.skills[0].label == "Languages"
        assert result.skills[0].skills == ["Python", "Go", "Rust"]

    def test_edit_skills_add_group(self) -> None:
        """Typing 'add' creates a new skill group."""
        content = self._make_skills_content()
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/goto 2",  # navigate to skills section
                "/edit",  # edit skills
                "add",  # add new group
                "Databases",  # new group label
                "PostgreSQL, Redis",  # new group skills
                "/accept",  # accept skills
                "/goto 1",  # back to mission
                "/accept",  # accept mission
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.skills) == 3
        assert result.skills[2].label == "Databases"
        assert result.skills[2].skills == ["PostgreSQL", "Redis"]

    def test_edit_skills_remove_group(self) -> None:
        """Typing 'remove N' removes the specified group after confirmation."""
        content = self._make_skills_content()
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/goto 2",  # navigate to skills section
                "/edit",  # edit skills
                "remove 2",  # remove group 2 (Cloud)
                "y",  # confirm removal
                "/accept",  # accept skills
                "/goto 1",  # back to mission
                "/accept",  # accept mission
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.skills) == 1
        assert result.skills[0].label == "Languages"

    def test_edit_skills_remove_cancelled(self) -> None:
        """Declining removal confirmation keeps skills unchanged."""
        content = self._make_skills_content()
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/goto 2",  # navigate to skills section
                "/edit",  # edit skills
                "remove 1",  # attempt to remove group 1
                "n",  # decline removal
                "/accept",  # accept skills unchanged
                "/goto 1",  # back to mission
                "/accept",  # accept mission
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.skills) == 2  # both groups still present

    def test_edit_skills_cancel(self) -> None:
        """Typing 'cancel' at group selection leaves skills unchanged."""
        content = self._make_skills_content()
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/goto 2",  # navigate to skills section
                "/edit",  # edit skills
                "cancel",  # cancel edit
                "/accept",  # accept skills unchanged
                "/goto 1",  # back to mission
                "/accept",  # accept mission
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.skills) == 2
        assert result.skills[0].label == "Languages"

    def test_edit_skills_empty_selection(self) -> None:
        """Empty input at group selection leaves skills unchanged."""
        content = self._make_skills_content()
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/goto 2",  # navigate to skills section
                "/edit",  # edit skills
                "",  # empty selection
                "/accept",  # accept skills unchanged
                "/goto 1",  # back to mission
                "/accept",  # accept mission
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.skills) == 2

    def test_edit_skills_invalid_group_number(self) -> None:
        """Invalid group number shows error and skills remain unchanged."""
        content = self._make_skills_content()
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/goto 2",  # navigate to skills section
                "/edit",  # edit skills
                "99",  # out of range group number
                "/accept",  # accept skills unchanged
                "/goto 1",  # back to mission
                "/accept",  # accept mission
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.skills) == 2

    def test_edit_skills_non_numeric_selection(self) -> None:
        """Non-numeric, non-keyword input shows error."""
        content = self._make_skills_content()
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/goto 2",  # navigate to skills section
                "/edit",  # edit skills
                "xyz",  # invalid selection
                "/accept",  # accept skills unchanged
                "/goto 1",  # back to mission
                "/accept",  # accept mission
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.skills) == 2

    def test_edit_skills_add_empty_label_cancels(self) -> None:
        """Adding a group with empty label cancels the add."""
        content = self._make_skills_content()
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/goto 2",  # navigate to skills section
                "/edit",  # edit skills
                "add",  # add new group
                "",  # empty label -> cancel
                "/accept",  # accept skills unchanged
                "/goto 1",  # back to mission
                "/accept",  # accept mission
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.skills) == 2  # no new group added

    def test_edit_skills_add_empty_skills_cancels(self) -> None:
        """Adding a group with empty skills list cancels the add."""
        content = self._make_skills_content()
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/goto 2",  # navigate to skills section
                "/edit",  # edit skills
                "add",  # add new group
                "Databases",  # label provided
                "",  # empty skills -> cancel
                "/accept",  # accept skills unchanged
                "/goto 1",  # back to mission
                "/accept",  # accept mission
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.skills) == 2  # no new group added

    def test_edit_skills_remove_invalid_number(self) -> None:
        """Remove with invalid number shows error."""
        content = self._make_skills_content()
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/goto 2",  # navigate to skills section
                "/edit",  # edit skills
                "remove abc",  # invalid number
                "/accept",  # accept skills unchanged
                "/goto 1",  # back to mission
                "/accept",  # accept mission
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.skills) == 2

    def test_edit_skills_remove_out_of_range(self) -> None:
        """Remove with out-of-range number shows error."""
        content = self._make_skills_content()
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/goto 2",  # navigate to skills section
                "/edit",  # edit skills
                "remove 5",  # out of range
                "/accept",  # accept skills unchanged
                "/goto 1",  # back to mission
                "/accept",  # accept mission
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.skills) == 2

    def test_edit_skills_remove_without_number(self) -> None:
        """'remove' without a number shows usage error."""
        content = self._make_skills_content()
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/goto 2",  # navigate to skills section
                "/edit",  # edit skills
                "remove",  # missing number
                "/accept",  # accept skills unchanged
                "/goto 1",  # back to mission
                "/accept",  # accept mission
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.skills) == 2

    def test_edit_skills_section_state_unchanged(self) -> None:
        """Editing skills does not change the section state (REQ-140)."""
        content = self._make_skills_content()
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/goto 2",  # navigate to skills section
                "/edit",  # edit skills
                "1",  # select group 1
                "New Label",  # new label
                "",  # keep skills
                # Skills section is still PENDING after edit
                "/accept",  # now accept
                "/goto 1",  # back to mission
                "/accept",  # accept mission
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        # Section was still pending after edit, then accepted
        assert session._sections[1].state == SectionState.ACCEPTED


class TestEditLanguages:
    """/edit on a languages section updates the languages list."""

    def test_edit_languages_replaces_list(self) -> None:
        """Comma-separated input replaces the entire languages list (REQ-130)."""
        content = _make_content(roles=0, with_skills=False, with_languages=True)
        # mission + languages = 2 sections
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit English, Spanish, French",  # edit languages inline
                "/accept",  # accept languages
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert result.languages == ["English", "Spanish", "French"]

    def test_edit_languages_with_prompt(self) -> None:
        """No inline args prompts user for comma-separated languages."""
        content = _make_content(roles=0, with_skills=False, with_languages=True)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit with no args -> prompts
                "German, Japanese",  # user types new languages
                "/accept",  # accept languages
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert result.languages == ["German", "Japanese"]

    def test_edit_languages_empty_input_unchanged(self) -> None:
        """Empty input leaves languages unchanged (REQ-130)."""
        content = _make_content(roles=0, with_skills=False, with_languages=True)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit with no args -> prompts
                "  ",  # empty/whitespace input -> cancel
                "/accept",  # accept languages unchanged
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert result.languages == ["English"]  # original value

    def test_edit_languages_adds_language(self) -> None:
        """User can add a language by including it in the replacement list."""
        content = _make_content(roles=0, with_skills=False, with_languages=True)
        # Original languages: ["English"]
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit English, Mandarin",  # include original + new
                "/accept",  # accept languages
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert result.languages == ["English", "Mandarin"]
        assert len(result.languages) == 2

    def test_edit_languages_removes_language(self) -> None:
        """User can remove a language by omitting it from the replacement list."""
        content = TailoredContent(
            mission=_make_mission(),
            skills=[],
            roles=[],
            languages=["English", "Spanish", "French"],
        )
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit English, French",  # omit Spanish
                "/accept",  # accept languages
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert result.languages == ["English", "French"]
        assert "Spanish" not in result.languages

    def test_edit_languages_strips_whitespace(self) -> None:
        """Extra whitespace around language names is stripped."""
        content = _make_content(roles=0, with_skills=False, with_languages=True)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit  English ,  Spanish  ,  French  ",  # extra whitespace
                "/accept",  # accept languages
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert result.languages == ["English", "Spanish", "French"]

    def test_edit_languages_does_not_change_section_state(self) -> None:
        """Editing languages does not auto-change section state (REQ-140)."""
        content = _make_content(roles=0, with_skills=False, with_languages=True)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit English, Spanish",  # edit languages
                "/accept",  # accept languages
                "y",  # confirm
            ],
        ):
            session.run()

        # Languages section is index 1 (mission=0, languages=1)
        assert session._sections[1].state == SectionState.ACCEPTED


class TestEditExperience:
    """/edit on experience section: bullets, summary, tech stack."""

    def _make_experience_content(
        self,
        *,
        num_bullets: int = 2,
        with_summary: bool = False,
        with_tech: bool = False,
    ) -> TailoredContent:
        """Helper that builds content with a role having multiple bullets."""
        bullets = [
            TailoredBullet(
                original=f"Original bullet {i}",
                rewritten=f"Rewritten bullet {i}",
                keywords_incorporated=["keyword"],
                confidence="high",
            )
            for i in range(num_bullets)
        ]
        role = TailoredRole(
            company="TestCorp",
            position="Staff Engineer",
            start_date="2020-01",
            end_date="2024-01",
            bullets=bullets,
            summary="Led platform team" if with_summary else None,
            tech_stack="Python, Kubernetes" if with_tech else None,
        )
        return TailoredContent(
            mission=_make_mission(),
            skills=[],
            roles=[role],
        )

    def test_edit_bullet_successfully(self) -> None:
        """Selecting a bullet number and providing new text updates it."""
        content = self._make_experience_content(num_bullets=2)
        session = InteractiveSession(content, _quiet_console())
        # Sections: mission (0), experience (1)

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit experience
                "2",  # select bullet 2
                "Improved deployment pipeline reducing time by 50%",  # new text
                "/accept",  # accept experience
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert (
            result.roles[0].bullets[1].rewritten
            == "Improved deployment pipeline reducing time by 50%"
        )
        assert result.roles[0].bullets[1].confidence == "medium"
        # Original field preserved
        assert result.roles[0].bullets[1].original == "Original bullet 1"
        # First bullet unchanged
        assert result.roles[0].bullets[0].rewritten == "Rewritten bullet 0"
        assert result.roles[0].bullets[0].confidence == "high"

    def test_edit_bullet_cancel(self) -> None:
        """Typing 'cancel' at bullet selection leaves experience unchanged."""
        content = self._make_experience_content(num_bullets=2)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit experience
                "cancel",  # cancel edit
                "/accept",  # accept experience unchanged
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert result.roles[0].bullets[0].rewritten == "Rewritten bullet 0"
        assert result.roles[0].bullets[1].rewritten == "Rewritten bullet 1"

    def test_edit_bullet_invalid_selection(self) -> None:
        """Non-numeric input shows error; experience unchanged."""
        content = self._make_experience_content(num_bullets=2)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit experience
                "xyz",  # invalid selection
                "/accept",  # accept experience unchanged
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.roles[0].bullets) == 2
        assert result.roles[0].bullets[0].rewritten == "Rewritten bullet 0"

    def test_edit_bullet_out_of_range(self) -> None:
        """Out-of-range bullet number shows error."""
        content = self._make_experience_content(num_bullets=2)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit experience
                "99",  # out of range
                "/accept",  # accept experience unchanged
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.roles[0].bullets) == 2

    def test_edit_bullet_empty_text_unchanged(self) -> None:
        """Empty replacement text leaves the bullet unchanged."""
        content = self._make_experience_content(num_bullets=2)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit experience
                "1",  # select bullet 1
                "  ",  # empty/whitespace -> no change
                "/accept",  # accept experience unchanged
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert result.roles[0].bullets[0].rewritten == "Rewritten bullet 0"
        assert result.roles[0].bullets[0].confidence == "high"  # not changed

    def test_edit_experience_add_bullet(self) -> None:
        """Typing 'add' creates a new bullet."""
        content = self._make_experience_content(num_bullets=1)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit experience
                "add",  # add new bullet
                "Mentored 3 junior engineers",  # new bullet text
                "/accept",  # accept experience
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.roles[0].bullets) == 2
        assert result.roles[0].bullets[1].rewritten == "Mentored 3 junior engineers"
        assert result.roles[0].bullets[1].original == "[user-added]"
        assert result.roles[0].bullets[1].confidence == "medium"
        assert result.roles[0].bullets[1].keywords_incorporated == []

    def test_edit_experience_add_bullet_empty_text(self) -> None:
        """Adding a bullet with empty text is rejected."""
        content = self._make_experience_content(num_bullets=1)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit experience
                "add",  # add new bullet
                "",  # empty text -> rejected
                "/accept",  # accept experience unchanged
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.roles[0].bullets) == 1  # no bullet added

    def test_edit_experience_remove_bullet(self) -> None:
        """Typing 'remove N' removes the specified bullet after confirmation."""
        content = self._make_experience_content(num_bullets=3)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit experience
                "remove 2",  # remove bullet 2
                "y",  # confirm removal
                "/accept",  # accept experience
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.roles[0].bullets) == 2
        # Bullet 0 and 2 remain (bullet 1 was removed)
        assert result.roles[0].bullets[0].rewritten == "Rewritten bullet 0"
        assert result.roles[0].bullets[1].rewritten == "Rewritten bullet 2"

    def test_edit_experience_remove_only_bullet_rejected(self) -> None:
        """Cannot remove the only bullet (EC-112 / AC-112)."""
        content = self._make_experience_content(num_bullets=1)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit experience
                "remove 1",  # attempt to remove only bullet
                "/accept",  # accept experience unchanged
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.roles[0].bullets) == 1  # bullet still there

    def test_edit_experience_remove_cancelled(self) -> None:
        """Declining removal confirmation keeps bullets unchanged."""
        content = self._make_experience_content(num_bullets=2)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit experience
                "remove 1",  # attempt to remove bullet 1
                "n",  # decline removal
                "/accept",  # accept experience unchanged
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.roles[0].bullets) == 2  # both bullets still there

    def test_edit_experience_summary(self) -> None:
        """Typing 'summary' edits the role summary."""
        content = self._make_experience_content(with_summary=True)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit experience
                "summary",  # edit summary
                "Led distributed systems team",  # new summary
                "/accept",  # accept experience
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert result.roles[0].summary == "Led distributed systems team"

    def test_edit_experience_tech_stack(self) -> None:
        """Typing 'tech' edits the role tech stack."""
        content = self._make_experience_content(with_tech=True)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit experience
                "tech",  # edit tech stack
                "Go, gRPC, PostgreSQL",  # new tech stack
                "/accept",  # accept experience
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert result.roles[0].tech_stack == "Go, gRPC, PostgreSQL"

    def test_edit_experience_empty_selection(self) -> None:
        """Empty input at bullet selection leaves experience unchanged."""
        content = self._make_experience_content(num_bullets=2)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit experience
                "",  # empty selection
                "/accept",  # accept experience unchanged
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        assert len(result.roles[0].bullets) == 2

    def test_edit_experience_does_not_change_section_state(self) -> None:
        """Editing experience does not auto-change section state (REQ-140)."""
        content = self._make_experience_content(num_bullets=2)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "/edit",  # edit experience
                "1",  # select bullet 1
                "New bullet text",  # replacement text
                # Section is still PENDING after edit
                "/accept",  # now accept
                "y",  # confirm
            ],
        ):
            result = session.run()

        assert result is not None
        # Experience section is index 1 (mission=0, experience=1)
        assert session._sections[1].state == SectionState.ACCEPTED


# ---------------------------------------------------------------------------
# Regeneration helpers
# ---------------------------------------------------------------------------


def _make_regen_context() -> RegenerationContext:
    """Build a minimal RegenerationContext for testing."""
    return RegenerationContext(
        jd_analysis={"company": "TestCo", "role_title": "Engineer"},
        ats_keywords=["python", "distributed"],
        kb_text="Some knowledge base text",
    )


def _make_mock_regen_service(
    return_content: TailoredContent | None = None,
    side_effect: Exception | None = None,
) -> MagicMock:
    """Build a mock RegenerationService.

    If return_content is given, regenerate_section returns it.
    If side_effect is given, regenerate_section raises it.
    """
    service = MagicMock()
    if side_effect is not None:
        service.regenerate_section = AsyncMock(side_effect=side_effect)
    elif return_content is not None:
        service.regenerate_section = AsyncMock(return_value=return_content)
    else:
        # Default: return the content unchanged
        service.regenerate_section = AsyncMock(
            side_effect=lambda content, **kwargs: content,
        )
    return service


# ---------------------------------------------------------------------------
# Regeneration dispatch tests
# ---------------------------------------------------------------------------


class TestRegenerationDispatch:
    """Tests for free-text and /regenerate triggering the regeneration service."""

    def test_free_text_triggers_regeneration(self) -> None:
        """Bare text with regen service calls regenerate_section."""
        content = _make_content(roles=0, with_skills=False)
        updated = content.model_copy(
            update={"mission": _make_mission().model_copy(update={"text": "Updated"})},
        )
        service = _make_mock_regen_service(return_content=updated)
        ctx = _make_regen_context()

        session = InteractiveSession(
            content,
            _quiet_console(),
            regeneration_service=service,
            regeneration_context=ctx,
        )

        with patch(_PROMPT_ASK, side_effect=["make it shorter", "/accept", "y"]):
            result = session.run()

        assert result is not None
        service.regenerate_section.assert_called_once()
        call_kwargs = service.regenerate_section.call_args
        assert call_kwargs.kwargs["section_type"] == "mission"
        assert call_kwargs.kwargs["instructions"] == ["make it shorter"]
        assert call_kwargs.kwargs["context"] is ctx
        assert result.mission.text == "Updated"

    def test_regenerate_command_with_args(self) -> None:
        """/regenerate <instructions> triggers the service."""
        content = _make_content(roles=0, with_skills=False)
        service = _make_mock_regen_service()
        ctx = _make_regen_context()

        session = InteractiveSession(
            content,
            _quiet_console(),
            regeneration_service=service,
            regeneration_context=ctx,
        )

        with patch(
            _PROMPT_ASK,
            side_effect=["/regenerate make it shorter", "/accept", "y"],
        ):
            result = session.run()

        assert result is not None
        service.regenerate_section.assert_called_once()
        call_kwargs = service.regenerate_section.call_args
        assert call_kwargs.kwargs["instructions"] == ["make it shorter"]

    def test_regenerate_no_args_no_history_shows_hint(self) -> None:
        """/regenerate with no args and no prior instructions shows usage hint."""
        content = _make_content(roles=0, with_skills=False)
        service = _make_mock_regen_service()
        ctx = _make_regen_context()

        session = InteractiveSession(
            content,
            _quiet_console(),
            regeneration_service=service,
            regeneration_context=ctx,
        )

        with patch(
            _PROMPT_ASK,
            side_effect=["/regenerate", "/accept", "y"],
        ):
            result = session.run()

        assert result is not None
        # Should NOT have been called — just showed a hint
        service.regenerate_section.assert_not_called()

    def test_regenerate_no_args_with_history_retries(self) -> None:
        """/regenerate with no args but existing instructions retries."""
        content = _make_content(roles=0, with_skills=False)
        service = _make_mock_regen_service()
        ctx = _make_regen_context()

        session = InteractiveSession(
            content,
            _quiet_console(),
            regeneration_service=service,
            regeneration_context=ctx,
        )

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "first instruction",  # free text -> regen call 1
                "/regenerate",  # no args, but instructions exist -> regen call 2
                "/accept",
                "y",
            ],
        ):
            result = session.run()

        assert result is not None
        assert service.regenerate_section.call_count == 2
        # Second call should have the accumulated instructions
        second_call = service.regenerate_section.call_args_list[1]
        assert second_call.kwargs["instructions"] == ["first instruction"]

    def test_instructions_accumulate_across_turns(self) -> None:
        """Multiple free-text inputs accumulate instructions for the same section."""
        content = _make_content(roles=0, with_skills=False)
        service = _make_mock_regen_service()
        ctx = _make_regen_context()

        session = InteractiveSession(
            content,
            _quiet_console(),
            regeneration_service=service,
            regeneration_context=ctx,
        )

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "make it shorter",  # free text -> regen call 1
                "emphasize cloud",  # free text -> regen call 2
                "/accept",
                "y",
            ],
        ):
            result = session.run()

        assert result is not None
        assert service.regenerate_section.call_count == 2
        # Second call includes both instructions
        second_call = service.regenerate_section.call_args_list[1]
        assert second_call.kwargs["instructions"] == [
            "make it shorter",
            "emphasize cloud",
        ]

    def test_instructions_persist_across_goto(self) -> None:
        """Instructions persist when navigating away and back."""
        content = _make_content(roles=1, with_skills=False)
        # Sections: mission (0), experience (1)
        service = _make_mock_regen_service()
        ctx = _make_regen_context()

        session = InteractiveSession(
            content,
            _quiet_console(),
            regeneration_service=service,
            regeneration_context=ctx,
        )

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "make it shorter",  # free text on mission -> regen
                "/goto 2",  # go to experience
                "/goto 1",  # back to mission
                "/regenerate",  # retry with existing instructions
                "/accept",  # accept mission
                "/accept",  # accept experience
                "y",
            ],
        ):
            result = session.run()

        assert result is not None
        # Should have 2 regen calls on the mission section
        assert service.regenerate_section.call_count == 2
        # Second call (retry) includes the previously accumulated instruction
        second_call = service.regenerate_section.call_args_list[1]
        assert second_call.kwargs["instructions"] == ["make it shorter"]

    def test_instructions_cleared_on_accept(self) -> None:
        """/accept clears regeneration instructions for that section."""
        content = _make_content(roles=1, with_skills=False)
        # Sections: mission (0), experience (1)
        service = _make_mock_regen_service()
        ctx = _make_regen_context()

        session = InteractiveSession(
            content,
            _quiet_console(),
            regeneration_service=service,
            regeneration_context=ctx,
        )

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "make it shorter",  # free text on mission -> regen
                "/accept",  # accept mission (clears instructions)
                "/accept",  # accept experience
                "y",
            ],
        ):
            session.run()

        # Instructions for section 0 should be cleared after accept
        assert 0 not in session._regen_instructions

    def test_regeneration_error_shows_message(self) -> None:
        """PipelineStageError from regen service shows error but doesn't crash."""
        content = _make_content(roles=0, with_skills=False)
        error = PipelineStageError(
            "LLM call failed",
            stage="regenerate_section",
            stage_number=0,
        )
        service = _make_mock_regen_service(side_effect=error)
        ctx = _make_regen_context()

        session = InteractiveSession(
            content,
            _quiet_console(),
            regeneration_service=service,
            regeneration_context=ctx,
        )

        with patch(
            _PROMPT_ASK,
            side_effect=["rewrite the bullets", "/accept", "y"],
        ):
            result = session.run()

        assert result is not None
        # The original content should be preserved
        assert result.mission.text == "Experienced engineer passionate about building."

    def test_regeneration_generic_error_shows_message(self) -> None:
        """Generic exception from regen service shows error but doesn't crash."""
        content = _make_content(roles=0, with_skills=False)
        service = _make_mock_regen_service(side_effect=RuntimeError("connection lost"))
        ctx = _make_regen_context()

        session = InteractiveSession(
            content,
            _quiet_console(),
            regeneration_service=service,
            regeneration_context=ctx,
        )

        with patch(
            _PROMPT_ASK,
            side_effect=["try again", "/accept", "y"],
        ):
            result = session.run()

        assert result is not None

    def test_regeneration_updates_content(self) -> None:
        """Successful regeneration replaces the content."""
        original = _make_content(roles=0, with_skills=False)
        updated_mission = MissionStatement(
            text="Concise mission statement",
            rationale="Shortened per user request",
        )
        updated_content = original.model_copy(update={"mission": updated_mission})
        service = _make_mock_regen_service(return_content=updated_content)
        ctx = _make_regen_context()

        session = InteractiveSession(
            original,
            _quiet_console(),
            regeneration_service=service,
            regeneration_context=ctx,
        )

        with patch(
            _PROMPT_ASK,
            side_effect=["make it concise", "/accept", "y"],
        ):
            result = session.run()

        assert result is not None
        assert result.mission.text == "Concise mission statement"

    def test_free_text_without_regen_service_shows_not_available(self) -> None:
        """Free text without regen service shows info, doesn't crash."""
        content = _make_content(roles=0, with_skills=False)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=["make it shorter", "/accept", "y"],
        ):
            result = session.run()

        assert result is not None

    def test_regenerate_without_regen_service_shows_not_available(self) -> None:
        """/regenerate without regen service shows info, doesn't crash."""
        content = _make_content(roles=0, with_skills=False)
        session = InteractiveSession(content, _quiet_console())

        with patch(
            _PROMPT_ASK,
            side_effect=["/regenerate fix it", "/accept", "y"],
        ):
            result = session.run()

        assert result is not None

    def test_experience_section_maps_correctly(self) -> None:
        """Regeneration on experience passes section_type and role_index."""
        content = _make_content(roles=1, with_skills=False)
        # Sections: mission (0), experience (1)
        service = _make_mock_regen_service()
        ctx = _make_regen_context()

        session = InteractiveSession(
            content,
            _quiet_console(),
            regeneration_service=service,
            regeneration_context=ctx,
        )

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "improve the bullets",  # free text on experience
                "/accept",  # accept experience
                "y",
            ],
        ):
            session.run()

        service.regenerate_section.assert_called_once()
        call_kwargs = service.regenerate_section.call_args
        assert call_kwargs.kwargs["section_type"] == "experience"
        assert call_kwargs.kwargs["role_index"] == 0

    def test_skills_section_maps_correctly(self) -> None:
        """Regeneration on skills section passes correct section_type."""
        content = _make_content(roles=0, with_skills=True)
        # Sections: mission (0), skills (1)
        service = _make_mock_regen_service()
        ctx = _make_regen_context()

        session = InteractiveSession(
            content,
            _quiet_console(),
            regeneration_service=service,
            regeneration_context=ctx,
        )

        with patch(
            _PROMPT_ASK,
            side_effect=[
                "/accept",  # accept mission
                "add more cloud skills",  # free text on skills
                "/accept",  # accept skills
                "y",
            ],
        ):
            session.run()

        service.regenerate_section.assert_called_once()
        call_kwargs = service.regenerate_section.call_args
        assert call_kwargs.kwargs["section_type"] == "skills"


# ---------------------------------------------------------------------------
# Prompt function (prompt_fn) tests
# ---------------------------------------------------------------------------


class TestPromptFn:
    """Tests that InteractiveSession uses prompt_fn when provided."""

    def test_prompt_fn_used_for_input(self) -> None:
        """When prompt_fn is provided, it is used instead of Prompt.ask."""
        content = _make_content(roles=0, with_skills=False)
        # Only mission section — accept then confirm done
        call_count = 0

        def mock_prompt_fn(label: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "/accept"
            return ""  # fallback

        session = InteractiveSession(
            content,
            _quiet_console(),
            prompt_fn=mock_prompt_fn,
        )

        # The finalize "y/n" prompt uses Prompt.ask directly, so we still
        # need to patch that for the done handler.
        with patch(_PROMPT_ASK, return_value="y"):
            result = session.run()

        assert result is not None
        # prompt_fn was called at least once for the REPL input
        assert call_count >= 1

    def test_session_works_without_prompt_fn(self) -> None:
        """When prompt_fn is None, session falls back to Prompt.ask."""
        content = _make_content(roles=0, with_skills=False)
        session = InteractiveSession(content, _quiet_console(), prompt_fn=None)

        with patch(_PROMPT_ASK, side_effect=["/accept", "y"]):
            result = session.run()

        assert result is not None

    def test_prompt_fn_receives_section_label(self) -> None:
        """The prompt_fn receives the section label as its argument."""
        content = _make_content(roles=0, with_skills=False)
        received_labels: list[str] = []

        def capture_prompt_fn(label: str) -> str:
            received_labels.append(label)
            return "/accept"

        session = InteractiveSession(
            content,
            _quiet_console(),
            prompt_fn=capture_prompt_fn,
        )

        with patch(_PROMPT_ASK, return_value="y"):
            session.run()

        # Should have received the prompt label for mission section
        assert len(received_labels) >= 1
        assert "Mission" in received_labels[0]
