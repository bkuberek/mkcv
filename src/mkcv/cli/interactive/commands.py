"""Slash-command parser for interactive resume review."""

from dataclasses import dataclass
from enum import Enum, auto


class CommandKind(Enum):
    """All recognised interactive commands."""

    ACCEPT = auto()
    SKIP = auto()
    EDIT = auto()
    DISPLAY = auto()
    SECTIONS = auto()
    GOTO = auto()
    DONE = auto()
    CANCEL = auto()
    HELP = auto()
    REGENERATE = auto()
    FREE_TEXT = auto()
    UNKNOWN = auto()


_COMMAND_MAP: dict[str, CommandKind] = {
    "/accept": CommandKind.ACCEPT,
    "/a": CommandKind.ACCEPT,
    "/skip": CommandKind.SKIP,
    "/s": CommandKind.SKIP,
    "/edit": CommandKind.EDIT,
    "/e": CommandKind.EDIT,
    "/display": CommandKind.DISPLAY,
    "/d": CommandKind.DISPLAY,
    "/sections": CommandKind.SECTIONS,
    "/goto": CommandKind.GOTO,
    "/g": CommandKind.GOTO,
    "/done": CommandKind.DONE,
    "/cancel": CommandKind.CANCEL,
    "/help": CommandKind.HELP,
    "/h": CommandKind.HELP,
    "/regenerate": CommandKind.REGENERATE,
    "/regen": CommandKind.REGENERATE,
}


@dataclass(frozen=True)
class ParsedCommand:
    """Result of parsing a raw input line."""

    kind: CommandKind
    args: str = ""


def parse(raw: str) -> ParsedCommand:
    """Parse a raw input string into a command.

    Rules:
    - Empty / whitespace-only input  ->  DISPLAY (re-render current section)
    - ``/command [args]``            ->  matching CommandKind with args
    - Unknown ``/something``         ->  UNKNOWN
    - Bare text (no leading ``/``)   ->  FREE_TEXT (regeneration instruction)
    """
    stripped = raw.strip()

    if not stripped:
        return ParsedCommand(kind=CommandKind.DISPLAY)

    if not stripped.startswith("/"):
        return ParsedCommand(kind=CommandKind.FREE_TEXT, args=stripped)

    parts = stripped.split(maxsplit=1)
    cmd_token = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    kind = _COMMAND_MAP.get(cmd_token, CommandKind.UNKNOWN)
    return ParsedCommand(kind=kind, args=args)
