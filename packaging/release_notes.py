"""Print the CHANGELOG.md section of one release: the notes of its GitHub release.

    python3 packaging/release_notes.py CHANGELOG.md v1.5.1 > notes.md

Exits 1 when the changelog has no section for the tag. Standard library only, so the
release workflow runs it with the runner's own Python.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SECTION_PREFIX = "## "


def release_notes(changelog: str, tag: str) -> str:
    """The lines between the `## <tag>` heading and the next `## ` heading, trimmed."""
    lines = changelog.splitlines()
    start = next((i for i, line in enumerate(lines) if _is_heading_of(line, tag)), None)
    if start is None:
        raise LookupError(f"the changelog has no section for {tag}")
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if lines[i].startswith(SECTION_PREFIX)
        ),
        len(lines),
    )
    return "\n".join(lines[start + 1 : end]).strip() + "\n"


def _is_heading_of(line: str, tag: str) -> bool:
    heading = SECTION_PREFIX + tag
    return line == heading or line.startswith(heading + " ")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("changelog", type=Path)
    parser.add_argument("tag", help="the release tag, e.g. v1.5.1")
    args = parser.parse_args(argv)
    try:
        notes = release_notes(args.changelog.read_text(encoding="utf-8"), args.tag)
    except LookupError as error:
        sys.exit(f"{args.changelog}: {error}")
    sys.stdout.write(notes)


if __name__ == "__main__":
    main()
