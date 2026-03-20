"""Tests for prompt_input module -- CommandCompleter and prompt factory."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from mkcv.cli.interactive.commands import _COMMAND_MAP
from mkcv.cli.interactive.prompt_input import (
    _COMMAND_DESCRIPTIONS,
    CommandCompleter,
    create_prompt_fn,
)
from mkcv.cli.interactive.sections import SectionInfo, SectionKind

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_sections() -> list[SectionInfo]:
    """Create a representative list of sections for testing."""
    return [
        SectionInfo(kind=SectionKind.MISSION, label="Mission"),
        SectionInfo(kind=SectionKind.SKILLS, label="Skills"),
        SectionInfo(
            kind=SectionKind.EXPERIENCE,
            label="Experience: Acme, Engineer",
            role_index=0,
        ),
        SectionInfo(
            kind=SectionKind.EARLIER_EXPERIENCE,
            label="Earlier Experience",
        ),
        SectionInfo(kind=SectionKind.LANGUAGES, label="Languages"),
    ]


def _get_completions(completer: CommandCompleter, text: str) -> list[str]:
    """Helper to get completion text values for a given input string."""
    doc = Document(text, len(text))
    event = CompleteEvent()
    return [c.text for c in completer.get_completions(doc, event)]


def _get_completions_with_meta(
    completer: CommandCompleter, text: str
) -> list[tuple[str, str]]:
    """Get (text, display_meta_text) pairs for completions."""
    doc = Document(text, len(text))
    event = CompleteEvent()
    results: list[tuple[str, str]] = []
    for c in completer.get_completions(doc, event):
        meta = c.display_meta
        if meta is None:
            meta_str = ""
        elif isinstance(meta, str):
            meta_str = meta
        else:
            # FormattedText: extract plain text from tuples
            meta_str = "".join(t[1] for t in meta)
        results.append((c.text, meta_str))
    return results


# ---------------------------------------------------------------------------
# CommandCompleter tests
# ---------------------------------------------------------------------------


class TestCommandCompleterSlashCommands:
    """Test slash-command prefix matching."""

    def test_slash_returns_all_commands(self) -> None:
        """Typing '/' alone should yield all commands."""
        completer = CommandCompleter(_make_sections())
        results = _get_completions(completer, "/")
        all_commands = sorted(_COMMAND_MAP.keys())
        assert results == all_commands

    def test_prefix_accept(self) -> None:
        """/ac should match /accept."""
        completer = CommandCompleter(_make_sections())
        results = _get_completions(completer, "/ac")
        assert "/accept" in results

    def test_prefix_skip_and_sections(self) -> None:
        """/s should match /skip and /sections."""
        completer = CommandCompleter(_make_sections())
        results = _get_completions(completer, "/s")
        assert "/skip" in results
        assert "/sections" in results

    def test_exact_command_matches(self) -> None:
        """/accept should still show /accept (exact match is a prefix match)."""
        completer = CommandCompleter(_make_sections())
        results = _get_completions(completer, "/accept")
        assert results == ["/accept"]

    def test_no_match_returns_empty(self) -> None:
        """/xyz should yield no completions."""
        completer = CommandCompleter(_make_sections())
        results = _get_completions(completer, "/xyz")
        assert results == []

    def test_case_insensitive(self) -> None:
        """/AC should match /accept (case insensitive)."""
        completer = CommandCompleter(_make_sections())
        results = _get_completions(completer, "/AC")
        assert "/accept" in results

    def test_case_insensitive_mixed(self) -> None:
        """/He should match /help."""
        completer = CommandCompleter(_make_sections())
        results = _get_completions(completer, "/He")
        assert "/help" in results

    def test_completions_include_display_meta(self) -> None:
        """Completions should include description metadata."""
        completer = CommandCompleter(_make_sections())
        results = _get_completions_with_meta(completer, "/accept")
        assert len(results) == 1
        text, meta = results[0]
        assert text == "/accept"
        assert meta == _COMMAND_DESCRIPTIONS["/accept"]

    def test_alias_commands_complete(self) -> None:
        """Alias commands like /a, /s, /e should complete."""
        completer = CommandCompleter(_make_sections())
        results = _get_completions(completer, "/a")
        assert "/a" in results
        assert "/accept" in results

    def test_regen_aliases_complete(self) -> None:
        """/re should match /regen and /regenerate."""
        completer = CommandCompleter(_make_sections())
        results = _get_completions(completer, "/re")
        assert "/regen" in results
        assert "/regenerate" in results


class TestCommandCompleterGoto:
    """Test /goto section-number completions."""

    def test_goto_space_shows_all_section_numbers(self) -> None:
        """'/goto ' should yield section numbers 1..N."""
        sections = _make_sections()
        completer = CommandCompleter(sections)
        results = _get_completions(completer, "/goto ")
        expected = [str(i) for i in range(1, len(sections) + 1)]
        assert results == expected

    def test_g_space_shows_all_section_numbers(self) -> None:
        """'/g ' should also yield section numbers (alias)."""
        sections = _make_sections()
        completer = CommandCompleter(sections)
        results = _get_completions(completer, "/g ")
        expected = [str(i) for i in range(1, len(sections) + 1)]
        assert results == expected

    def test_goto_partial_number_filters(self) -> None:
        """'/goto 1' should yield only '1' (with 5 sections)."""
        sections = _make_sections()
        completer = CommandCompleter(sections)
        results = _get_completions(completer, "/goto 1")
        assert results == ["1"]

    def test_goto_number_has_section_label_meta(self) -> None:
        """Section number completions should include section labels."""
        sections = _make_sections()
        completer = CommandCompleter(sections)
        results = _get_completions_with_meta(completer, "/goto ")
        # First section should be Mission
        assert results[0] == ("1", "Mission")
        assert results[1] == ("2", "Skills")

    def test_goto_no_match_for_nonexistent_number(self) -> None:
        """'/goto 9' with 5 sections yields nothing."""
        sections = _make_sections()
        completer = CommandCompleter(sections)
        results = _get_completions(completer, "/goto 9")
        assert results == []

    def test_goto_case_insensitive(self) -> None:
        """'/GOTO ' should work (case-insensitive prefix check)."""
        sections = _make_sections()
        completer = CommandCompleter(sections)
        results = _get_completions(completer, "/GOTO ")
        expected = [str(i) for i in range(1, len(sections) + 1)]
        assert results == expected


class TestCommandCompleterBareText:
    """Test that bare text (no leading /) yields no completions."""

    def test_no_completion_for_bare_text(self) -> None:
        """'make it shorter' should yield no completions."""
        completer = CommandCompleter(_make_sections())
        results = _get_completions(completer, "make it shorter")
        assert results == []

    def test_no_completion_for_empty_string(self) -> None:
        """Empty string should yield no completions."""
        completer = CommandCompleter(_make_sections())
        results = _get_completions(completer, "")
        assert results == []

    def test_no_completion_for_whitespace(self) -> None:
        """Whitespace-only input should yield no completions."""
        completer = CommandCompleter(_make_sections())
        results = _get_completions(completer, "   ")
        assert results == []


# ---------------------------------------------------------------------------
# create_prompt_fn tests
# ---------------------------------------------------------------------------


class TestCreatePromptFn:
    """Test the prompt factory function."""

    def test_returns_none_when_not_tty(self) -> None:
        """Should return None when stdin is not a TTY."""
        with patch("mkcv.cli.interactive.prompt_input.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            result = create_prompt_fn(_make_sections())
            assert result is None

    def test_returns_callable_when_tty(self) -> None:
        """Should return a callable when TTY and prompt_toolkit ok."""
        with patch("mkcv.cli.interactive.prompt_input.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = True
            result = create_prompt_fn(_make_sections())
            assert result is not None
            assert callable(result)

    def test_returns_none_when_prompt_toolkit_unavailable(self) -> None:
        """Should return None when _HAS_PROMPT_TOOLKIT is False."""
        with patch(
            "mkcv.cli.interactive.prompt_input._HAS_PROMPT_TOOLKIT", False
        ):
            result = create_prompt_fn(_make_sections())
            assert result is None

    def test_prompt_fn_calls_session_prompt(self) -> None:
        """The returned callable should invoke PromptSession.prompt()."""
        with (
            patch("mkcv.cli.interactive.prompt_input.sys") as mock_sys,
            patch("prompt_toolkit.PromptSession") as mock_session_cls,
        ):
            mock_sys.stdin.isatty.return_value = True
            mock_instance = mock_session_cls.return_value
            mock_instance.prompt.return_value = "/accept"

            fn = create_prompt_fn(_make_sections())
            assert fn is not None

            result = fn("[1/5] Mission")
            assert result == "/accept"
            mock_instance.prompt.assert_called_once_with(
                "[1/5] Mission > ",
            )

    def test_prompt_fn_converts_eof_to_keyboard_interrupt(
        self,
    ) -> None:
        """EOFError from prompt_toolkit should raise KeyboardInterrupt."""
        with (
            patch("mkcv.cli.interactive.prompt_input.sys") as mock_sys,
            patch("prompt_toolkit.PromptSession") as mock_session_cls,
        ):
            mock_sys.stdin.isatty.return_value = True
            mock_instance = mock_session_cls.return_value
            mock_instance.prompt.side_effect = EOFError

            fn = create_prompt_fn(_make_sections())
            assert fn is not None

            with pytest.raises(KeyboardInterrupt):
                fn("[1/5] Mission")
