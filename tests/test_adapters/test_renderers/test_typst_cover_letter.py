"""Tests for TypstCoverLetterRenderer."""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from mkcv.adapters.renderers.typst_cover_letter import (
    TypstCoverLetterRenderer,
    escape_typst,
)
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


class TestEscapeTypst:
    """Tests for the escape_typst helper function."""

    def test_escapes_dollar_sign(self) -> None:
        assert escape_typst("earned $4B+") == r"earned \$4B+"

    def test_escapes_hash(self) -> None:
        assert escape_typst("issue #42") == r"issue \#42"

    def test_escapes_at_sign(self) -> None:
        assert escape_typst("contact @team") == r"contact \@team"

    def test_escapes_asterisk(self) -> None:
        assert escape_typst("important *note*") == r"important \*note\*"

    def test_escapes_underscore(self) -> None:
        assert escape_typst("snake_case_name") == r"snake\_case\_name"

    def test_escapes_backslash(self) -> None:
        assert escape_typst(r"path\to\file") == r"path\\to\\file"

    def test_escapes_backtick(self) -> None:
        assert escape_typst("use `code` here") == r"use \`code\` here"

    def test_escapes_angle_brackets(self) -> None:
        assert escape_typst("a <tag> value") == r"a \<tag\> value"

    def test_escapes_tilde(self) -> None:
        assert escape_typst("approx ~100") == r"approx \~100"

    def test_escapes_square_brackets(self) -> None:
        assert escape_typst("see [ref]") == r"see \[ref\]"

    def test_escapes_curly_braces(self) -> None:
        assert escape_typst("dict {key}") == r"dict \{key\}"

    def test_leaves_plain_text_unchanged(self) -> None:
        plain = "Hello, I have 8 years of experience in Python."
        assert escape_typst(plain) == plain

    def test_handles_empty_string(self) -> None:
        assert escape_typst("") == ""

    def test_escapes_multiple_special_chars(self) -> None:
        text = "earned $4B+ at #1 company @scale"
        assert escape_typst(text) == r"earned \$4B+ at \#1 company \@scale"

    def test_real_world_cover_letter_content(self) -> None:
        """Reproduce the actual bug: LLM output with $ signs."""
        text = (
            "NovaCraft's platform processes $4B+ in annual transaction "
            "volume while maintaining sub-100ms p99 latency"
        )
        escaped = escape_typst(text)
        # The dollar sign must be escaped so Typst doesn't enter math mode
        assert r"\$4B+" in escaped
        # No unescaped dollar signs remain
        assert escaped.count("$") == escaped.count(r"\$")


class TestTypstCoverLetterRendererEscaping:
    """Verify the renderer escapes special characters in LLM content."""

    def test_typ_source_escapes_dollar_in_paragraph(
        self,
        renderer: TypstCoverLetterRenderer,
        mock_typst_module: ModuleType,
        tmp_path: Path,
    ) -> None:
        """Dollar signs in body text must be escaped in the .typ output."""
        letter = CoverLetter(
            company="FinCorp",
            role_title="Engineer",
            salutation="Dear Hiring Manager,",
            opening_paragraph="We process $4B+ in revenue.",
            body_paragraphs=["Scaled to $10M ARR in 2 years."],
            closing_paragraph="Looking forward to connecting.",
            sign_off="Best,",
            candidate_name="Alex Chen",
        )
        output_dir = tmp_path / "output"
        with patch.dict(sys.modules, {"typst": mock_typst_module}):
            renderer.render(letter, output_dir)

        typ_content = (output_dir / "cover_letter.typ").read_text(encoding="utf-8")
        # Dollar signs in content must be backslash-escaped
        assert r"\$4B+" in typ_content
        assert r"\$10M" in typ_content

    def test_typ_source_escapes_hash_in_company(
        self,
        renderer: TypstCoverLetterRenderer,
        mock_typst_module: ModuleType,
        tmp_path: Path,
    ) -> None:
        """Hash in company name must be escaped to avoid Typst function calls."""
        letter = CoverLetter(
            company="Company #1",
            role_title="Role",
            salutation="Hi,",
            opening_paragraph="Great role.",
            body_paragraphs=["Body."],
            closing_paragraph="Thanks.",
            sign_off="Best,",
            candidate_name="Test User",
        )
        output_dir = tmp_path / "output"
        with patch.dict(sys.modules, {"typst": mock_typst_module}):
            renderer.render(letter, output_dir)

        typ_content = (output_dir / "cover_letter.typ").read_text(encoding="utf-8")
        assert r"Company \#1" in typ_content

    def test_typ_source_escapes_special_chars_in_all_fields(
        self,
        renderer: TypstCoverLetterRenderer,
        mock_typst_module: ModuleType,
        tmp_path: Path,
    ) -> None:
        """All content fields must have special chars escaped."""
        letter = CoverLetter(
            company="Acme $Corp",
            role_title="Dev #Lead",
            salutation="Dear @team,",
            opening_paragraph="We use *bold* moves.",
            body_paragraphs=["Check [this] out.", "Use {braces} here."],
            closing_paragraph="See <link> for details.",
            sign_off="Thanks~",
            candidate_name="Jane_Doe",
        )
        output_dir = tmp_path / "output"
        with patch.dict(sys.modules, {"typst": mock_typst_module}):
            renderer.render(letter, output_dir)

        typ_content = (output_dir / "cover_letter.typ").read_text(encoding="utf-8")
        assert r"\$Corp" in typ_content
        assert r"\#Lead" in typ_content
        assert r"\@team" in typ_content
        assert r"\*bold\*" in typ_content
        assert r"\[this\]" in typ_content
        assert r"\{braces\}" in typ_content
        assert r"\<link\>" in typ_content
        assert r"Thanks\~" in typ_content
        assert r"Jane\_Doe" in typ_content
