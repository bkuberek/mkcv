"""Tab-completion prompt wrapper for interactive resume review.

Provides a ``CommandCompleter`` that offers prefix-matching completions for
slash commands, and a factory function that builds a prompt_toolkit-based
prompt callable with graceful fallback when prompt_toolkit is unavailable
or stdin is not a TTY.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from mkcv.cli.interactive.commands import _COMMAND_MAP

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from mkcv.cli.interactive.sections import SectionInfo

logger = logging.getLogger(__name__)

# Description metadata for each command, used as display_meta in completions.
_COMMAND_DESCRIPTIONS: dict[str, str] = {
    "/accept": "Accept current section",
    "/a": "Alias for /accept",
    "/skip": "Skip current section",
    "/s": "Alias for /skip",
    "/edit": "Edit current section",
    "/e": "Alias for /edit",
    "/display": "Re-display current section",
    "/d": "Alias for /display",
    "/sections": "Show all sections overview",
    "/goto": "Jump to section N",
    "/g": "Alias for /goto",
    "/done": "Finish review",
    "/cancel": "Cancel and discard changes",
    "/help": "Show help",
    "/h": "Alias for /help",
    "/regenerate": "Regenerate section: /regenerate <instructions>",
    "/regen": "Alias for /regenerate",
}


try:
    from prompt_toolkit.completion import CompleteEvent, Completer, Completion
    from prompt_toolkit.document import Document  # noqa: TC002

    _HAS_PROMPT_TOOLKIT = True
except ImportError:  # pragma: no cover
    _HAS_PROMPT_TOOLKIT = False


if _HAS_PROMPT_TOOLKIT:

    class CommandCompleter(Completer):
        """Prefix-matching completer for interactive slash commands.

        Completes ``/`` commands from ``_COMMAND_MAP`` and offers section
        numbers after ``/goto`` or ``/g``.

        Args:
            sections: List of section metadata for ``/goto`` number completions.
        """

        def __init__(self, sections: list[SectionInfo]) -> None:
            self._commands = sorted(_COMMAND_MAP.keys())
            self._sections = sections

        def get_completions(
            self,
            document: Document,
            complete_event: CompleteEvent,
        ) -> Iterable[Completion]:
            """Yield matching completions for the current input."""
            text = document.text_before_cursor

            # Only complete when input starts with "/"
            if not text.startswith("/"):
                return

            # Check for "/goto <arg>" or "/g <arg>" completion of section numbers
            text_lower = text.lower()
            for prefix in ("/goto ", "/g "):
                if text_lower.startswith(prefix):
                    partial_num = text[len(prefix):]
                    yield from self._goto_completions(partial_num)
                    return

            # Slash-command prefix matching (case-insensitive)
            partial = text.lower()
            for cmd in self._commands:
                if cmd.startswith(partial):
                    desc = _COMMAND_DESCRIPTIONS.get(cmd, "")
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display_meta=desc,
                    )

        def _goto_completions(self, partial: str) -> Iterable[Completion]:
            """Yield section-number completions for ``/goto``."""
            for i, section in enumerate(self._sections, 1):
                num_str = str(i)
                if num_str.startswith(partial):
                    yield Completion(
                        num_str,
                        start_position=-len(partial),
                        display_meta=section.label,
                    )


def create_prompt_fn(
    sections: list[SectionInfo],
) -> Callable[[str], str] | None:
    """Create a prompt_toolkit-based prompt function with tab completion.

    Returns ``None`` if ``prompt_toolkit`` is not available or if stdin
    is not a TTY.  The caller should fall back to ``Prompt.ask`` in that case.
    """
    if not _HAS_PROMPT_TOOLKIT:
        return None

    if not sys.stdin.isatty():
        return None

    from prompt_toolkit import PromptSession

    completer = CommandCompleter(sections)
    session: PromptSession[str] = PromptSession(completer=completer)

    def _prompt_fn(label: str) -> str:
        try:
            return session.prompt(f"{label} > ")
        except EOFError:
            raise KeyboardInterrupt from None

    return _prompt_fn
