"""Render Formula/mkcv.rb for one release from mkcv.rb.template.

The formula installs the release's wheel and its hashed requirements file, both served
under BASE_URL by their file names; the sha256 of each is read from the local copy:

    python3 packaging/homebrew/render_formula.py \\
        --base-url https://github.com/bkuberek/mkcv/releases/download/v1.5.1 \\
        --wheel dist/mkcv-1.5.1-py3-none-any.whl \\
        --requirements dist/requirements.txt \\
        --output Formula/mkcv.rb

Standard library only, so the release workflow runs it with the runner's own Python.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from string import Template
from urllib.parse import quote

TEMPLATE = Path(__file__).with_name("mkcv.rb.template")
REQUIREMENTS_NAME = "requirements.txt"


@dataclass(frozen=True, slots=True)
class ReleaseFiles:
    base_url: str
    wheel: Path
    requirements: Path


def render_formula(release: ReleaseFiles, template: str) -> str:
    """Fill the template; a placeholder without a value raises KeyError."""
    _check_names(release)
    return Template(template).substitute(
        wheel_name=release.wheel.name,
        wheel_url=_url(release.base_url, release.wheel),
        wheel_sha256=_sha256(release.wheel),
        requirements_url=_url(release.base_url, release.requirements),
        requirements_sha256=_sha256(release.requirements),
    )


def _check_names(release: ReleaseFiles) -> None:
    if not release.wheel.name.endswith("-py3-none-any.whl"):
        raise ValueError(
            f"{release.wheel.name} is not a pure-Python wheel (*-py3-none-any.whl)"
        )
    if release.requirements.name != REQUIREMENTS_NAME:
        raise ValueError(f"the requirements file must be named {REQUIREMENTS_NAME}")


def _url(base_url: str, file: Path) -> str:
    return f"{base_url.rstrip('/')}/{quote(file.name)}"


def _sha256(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base-url", required=True, help="URL the release files are served under"
    )
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--requirements", required=True, type=Path)
    parser.add_argument(
        "--output", type=Path, help="formula file to write (default: stdout)"
    )
    args = parser.parse_args(argv)
    release = ReleaseFiles(args.base_url, args.wheel, args.requirements)
    formula = render_formula(release, TEMPLATE.read_text(encoding="utf-8"))
    if args.output is None:
        sys.stdout.write(formula)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(formula, encoding="utf-8")


if __name__ == "__main__":
    main()
