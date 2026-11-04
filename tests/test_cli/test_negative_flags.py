"""Negative boolean flags must turn their option off, not on."""

import pytest

from mkcv.cli.app import app


@pytest.mark.parametrize(
    ("argv", "param", "expected"),
    [
        (["generate", "--no-render"], "render", False),
        (["generate", "--render"], "render", True),
        (["generate", "--no-interactive"], "interactive", False),
        (["generate", "--interactive"], "interactive", True),
        (["generate", "-i"], "interactive", True),
        (["generate", "--no-cover-letter"], "cover_letter", False),
        (["generate", "--cover-letter"], "cover_letter", True),
        (["cover-letter", "--jd", "jd.md", "--no-render"], "render", False),
        (["cover-letter", "--jd", "jd.md", "--render"], "render", True),
    ],
)
def test_boolean_flag_parses_to_expected_value(
    argv: list[str], param: str, expected: bool
) -> None:
    _, bound, _ = app.parse_args(argv)

    assert bound.arguments[param] is expected


def test_interactive_defaults_to_unset_so_tty_detection_applies() -> None:
    _, bound, _ = app.parse_args(["generate"])

    assert "interactive" not in bound.arguments
