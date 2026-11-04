"""Tests for the release tooling in packaging/.

The scripts are loaded by file path: their directory is named `packaging`, which would
otherwise collide with the PyPA `packaging` library.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

PACKAGING = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve their module through sys.modules.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


release_notes = _load("release_notes", PACKAGING / "release_notes.py")
render_formula = _load("render_formula", PACKAGING / "homebrew" / "render_formula.py")

CHANGELOG = """# Changelog

<!-- version list -->

## v1.5.1 (2026-11-04)

### Bug Fixes

- **cli**: Negative boolean flags turned options on

## v1.5.0 (2026-11-04)

### Features

- Provider-agnostic models
"""


class TestReleaseNotes:
    def test_returns_only_the_requested_section(self) -> None:
        notes = release_notes.release_notes(CHANGELOG, "v1.5.1")

        assert notes == (
            "### Bug Fixes\n\n- **cli**: Negative boolean flags turned options on\n"
        )

    def test_last_section_runs_to_the_end(self) -> None:
        notes = release_notes.release_notes(CHANGELOG, "v1.5.0")

        assert notes.endswith("- Provider-agnostic models\n")

    def test_tag_is_not_matched_as_a_prefix(self) -> None:
        with pytest.raises(LookupError):
            release_notes.release_notes(CHANGELOG, "v1.5")

    def test_missing_tag_raises(self) -> None:
        with pytest.raises(LookupError, match=r"v9\.9\.9"):
            release_notes.release_notes(CHANGELOG, "v9.9.9")


class TestRenderFormula:
    @pytest.fixture
    def files(self, tmp_path: Path) -> render_formula.ReleaseFiles:
        wheel = tmp_path / "mkcv-1.5.1-py3-none-any.whl"
        requirements = tmp_path / "requirements.txt"
        wheel.write_bytes(b"wheel")
        requirements.write_bytes(b"requirements")
        return render_formula.ReleaseFiles(
            "https://example.test/v1.5.1/", wheel, requirements
        )

    def test_fills_urls_and_checksums(self, files: render_formula.ReleaseFiles) -> None:
        template = (
            "${wheel_url} ${wheel_sha256} ${requirements_url} ${requirements_sha256}"
        )

        formula = render_formula.render_formula(files, template)

        assert formula == (
            "https://example.test/v1.5.1/mkcv-1.5.1-py3-none-any.whl "
            f"{hashlib.sha256(b'wheel').hexdigest()} "
            "https://example.test/v1.5.1/requirements.txt "
            f"{hashlib.sha256(b'requirements').hexdigest()}"
        )

    def test_real_template_renders_without_leftover_placeholders(
        self, files: render_formula.ReleaseFiles
    ) -> None:
        template = render_formula.TEMPLATE.read_text(encoding="utf-8")

        formula = render_formula.render_formula(files, template)

        assert "${" not in formula
        assert 'bin.install_symlink libexec/"bin/mkcv"' in formula

    def test_rejects_a_platform_wheel(self, tmp_path: Path) -> None:
        wheel = tmp_path / "mkcv-1.5.1-cp313-cp313-macosx_11_0_arm64.whl"
        requirements = tmp_path / "requirements.txt"
        wheel.write_bytes(b"x")
        requirements.write_bytes(b"x")
        release = render_formula.ReleaseFiles(
            "https://example.test", wheel, requirements
        )

        with pytest.raises(ValueError, match="pure-Python wheel"):
            render_formula.render_formula(release, "")

    def test_rejects_a_misnamed_requirements_file(self, tmp_path: Path) -> None:
        wheel = tmp_path / "mkcv-1.5.1-py3-none-any.whl"
        requirements = tmp_path / "reqs.txt"
        wheel.write_bytes(b"x")
        requirements.write_bytes(b"x")
        release = render_formula.ReleaseFiles(
            "https://example.test", wheel, requirements
        )

        with pytest.raises(ValueError, match=r"requirements\.txt"):
            render_formula.render_formula(release, "")
