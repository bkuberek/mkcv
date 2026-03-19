"""Tests for TypstCoverLetterRenderer."""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from mkcv.adapters.renderers.typst_cover_letter import TypstCoverLetterRenderer
from mkcv.core.exceptions.render import RenderError
from mkcv.core.models.cover_letter import CoverLetter
from mkcv.core.ports.cover_letter_renderer import (
    CoverLetterRenderedOutput,
    CoverLetterRendererPort,
)


@pytest.fixture
def renderer() -> TypstCoverLetterRenderer:
    """Create a TypstCoverLetterRenderer instance."""
    return TypstCoverLetterRenderer()


@pytest.fixture
def sample_cover_letter() -> CoverLetter:
    """Build a sample cover letter for rendering tests."""
    return CoverLetter(
        company="TestCorp",
        role_title="Senior Software Engineer",
        salutation="Dear Hiring Manager,",
        opening_paragraph="I am excited to apply for this role.",
        body_paragraphs=[
            "I have 8 years of experience in Python.",
            "At my previous role, I led a team of 5 engineers.",
        ],
        closing_paragraph="I look forward to discussing this opportunity.",
        sign_off="Sincerely,",
        candidate_name="Jane Doe",
    )


@pytest.fixture
def mock_typst_module() -> ModuleType:
    """Create a mock typst module with a compile function."""
    mock_mod = ModuleType("typst")
    mock_mod.compile = MagicMock(return_value=b"%PDF-1.4 fake pdf content")  # type: ignore[attr-defined]
    return mock_mod


class TestTypstCoverLetterRendererProtocol:
    """Verify TypstCoverLetterRenderer satisfies CoverLetterRendererPort."""

    def test_implements_cover_letter_renderer_port(
        self, renderer: TypstCoverLetterRenderer
    ) -> None:
        assert isinstance(renderer, CoverLetterRendererPort)


class TestTypstCoverLetterRendererRender:
    """Tests for rendering with mocked typst compilation."""

    def test_render_produces_pdf(
        self,
        renderer: TypstCoverLetterRenderer,
        sample_cover_letter: CoverLetter,
        mock_typst_module: ModuleType,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        with patch.dict(sys.modules, {"typst": mock_typst_module}):
            result = renderer.render(sample_cover_letter, output_dir)

        assert isinstance(result, CoverLetterRenderedOutput)
        assert result.pdf_path.exists()
        assert result.pdf_path.suffix == ".pdf"

    def test_render_writes_typ_source(
        self,
        renderer: TypstCoverLetterRenderer,
        sample_cover_letter: CoverLetter,
        mock_typst_module: ModuleType,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        with patch.dict(sys.modules, {"typst": mock_typst_module}):
            renderer.render(sample_cover_letter, output_dir)

        typ_path = output_dir / "cover_letter.typ"
        assert typ_path.is_file()

    def test_render_typ_contains_candidate_name(
        self,
        renderer: TypstCoverLetterRenderer,
        sample_cover_letter: CoverLetter,
        mock_typst_module: ModuleType,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        with patch.dict(sys.modules, {"typst": mock_typst_module}):
            renderer.render(sample_cover_letter, output_dir)

        typ_path = output_dir / "cover_letter.typ"
        content = typ_path.read_text(encoding="utf-8")
        assert "Jane Doe" in content

    def test_render_creates_output_directory(
        self,
        renderer: TypstCoverLetterRenderer,
        sample_cover_letter: CoverLetter,
        mock_typst_module: ModuleType,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "nested" / "output"
        with patch.dict(sys.modules, {"typst": mock_typst_module}):
            renderer.render(sample_cover_letter, output_dir)

        assert output_dir.is_dir()


class TestTypstCoverLetterRendererErrors:
    """Tests for error handling in TypstCoverLetterRenderer."""

    def test_render_raises_for_typst_compilation_failure(
        self,
        renderer: TypstCoverLetterRenderer,
        sample_cover_letter: CoverLetter,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        failing_mod = ModuleType("typst")
        failing_mod.compile = MagicMock(side_effect=RuntimeError("compilation error"))  # type: ignore[attr-defined]

        with (
            patch.dict(sys.modules, {"typst": failing_mod}),
            pytest.raises(RenderError, match="Typst compilation failed"),
        ):
            renderer.render(sample_cover_letter, output_dir)

    def test_render_raises_when_typst_not_installed(
        self,
        renderer: TypstCoverLetterRenderer,
        sample_cover_letter: CoverLetter,
        tmp_path: Path,
    ) -> None:
        output_dir = tmp_path / "output"
        with (
            patch.dict(sys.modules, {"typst": None}),
            pytest.raises(RenderError, match="typst Python package is not installed"),
        ):
            renderer.render(sample_cover_letter, output_dir)
