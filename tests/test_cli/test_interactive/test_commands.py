"""Tests for the interactive command parser."""

import pytest

from mkcv.cli.interactive.commands import CommandKind, ParsedCommand, parse


class TestParseSlashCommands:
    """Every full slash command maps to the correct CommandKind."""

    @pytest.mark.parametrize(
        ("raw", "expected_kind"),
        [
            ("/accept", CommandKind.ACCEPT),
            ("/skip", CommandKind.SKIP),
            ("/edit", CommandKind.EDIT),
            ("/display", CommandKind.DISPLAY),
            ("/sections", CommandKind.SECTIONS),
            ("/goto", CommandKind.GOTO),
            ("/done", CommandKind.DONE),
            ("/cancel", CommandKind.CANCEL),
            ("/help", CommandKind.HELP),
            ("/regenerate", CommandKind.REGENERATE),
        ],
    )
    def test_full_commands(self, raw: str, expected_kind: CommandKind) -> None:
        result = parse(raw)
        assert result.kind == expected_kind

    @pytest.mark.parametrize(
        ("raw", "expected_kind"),
        [
            ("/a", CommandKind.ACCEPT),
            ("/s", CommandKind.SKIP),
            ("/e", CommandKind.EDIT),
            ("/d", CommandKind.DISPLAY),
            ("/g", CommandKind.GOTO),
            ("/h", CommandKind.HELP),
            ("/regen", CommandKind.REGENERATE),
        ],
    )
    def test_short_aliases(self, raw: str, expected_kind: CommandKind) -> None:
        result = parse(raw)
        assert result.kind == expected_kind


class TestParseCaseInsensitivity:
    """Commands are case-insensitive."""

    @pytest.mark.parametrize(
        "raw",
        ["/Accept", "/SKIP", "/Help", "/DONE", "/Cancel", "/EDIT"],
    )
    def test_mixed_case_commands(self, raw: str) -> None:
        result = parse(raw)
        assert result.kind != CommandKind.UNKNOWN


class TestParseArgs:
    """Arguments are correctly extracted from commands."""

    def test_goto_with_number(self) -> None:
        result = parse("/goto 3")
        assert result.kind == CommandKind.GOTO
        assert result.args == "3"

    def test_goto_without_args(self) -> None:
        result = parse("/goto")
        assert result.kind == CommandKind.GOTO
        assert result.args == ""

    def test_regenerate_with_prompt_text(self) -> None:
        result = parse("/regenerate some prompt text")
        assert result.kind == CommandKind.REGENERATE
        assert result.args == "some prompt text"

    def test_edit_with_inline_text(self) -> None:
        result = parse("/edit new mission text here")
        assert result.kind == CommandKind.EDIT
        assert result.args == "new mission text here"


class TestParseSpecialInput:
    """Edge-case inputs are handled correctly."""

    def test_empty_input_returns_display(self) -> None:
        result = parse("")
        assert result.kind == CommandKind.DISPLAY

    def test_whitespace_only_returns_display(self) -> None:
        result = parse("   ")
        assert result.kind == CommandKind.DISPLAY

    def test_unknown_slash_command(self) -> None:
        result = parse("/foo")
        assert result.kind == CommandKind.UNKNOWN

    def test_bare_text_without_slash(self) -> None:
        result = parse("some bare text")
        assert result.kind == CommandKind.UNKNOWN
        assert result.args == "some bare text"

    def test_leading_whitespace_is_stripped(self) -> None:
        result = parse("  /accept  ")
        assert result.kind == CommandKind.ACCEPT


class TestParsedCommandDataclass:
    """ParsedCommand is a frozen dataclass with correct defaults."""

    def test_default_args_is_empty_string(self) -> None:
        cmd = ParsedCommand(kind=CommandKind.ACCEPT)
        assert cmd.args == ""

    def test_frozen_immutability(self) -> None:
        cmd = ParsedCommand(kind=CommandKind.ACCEPT, args="test")
        with pytest.raises(AttributeError):
            cmd.kind = CommandKind.SKIP  # type: ignore[misc]
