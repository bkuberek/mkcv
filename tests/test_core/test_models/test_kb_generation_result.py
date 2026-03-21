"""Tests for KBGenerationResult model."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from mkcv.core.models.document_content import DocumentContent
from mkcv.core.models.kb_generation_result import KBGenerationResult


def _make_doc(name: str = "test.txt", text: str = "content") -> DocumentContent:
    """Create a sample DocumentContent for testing."""
    return DocumentContent(
        text=text,
        source_path=Path(f"/tmp/{name}"),
        format="text",
        char_count=len(text),
    )


class TestKBGenerationResultValid:
    """Tests for valid KBGenerationResult creation."""

    def test_minimal_valid_instance(self) -> None:
        result = KBGenerationResult(
            kb_text="# Career KB\n\n## Summary\nTest.",
            source_documents=[_make_doc()],
        )
        assert result.kb_text.startswith("# Career KB")
        assert len(result.source_documents) == 1

    def test_output_path_defaults_to_none(self) -> None:
        result = KBGenerationResult(
            kb_text="# KB",
            source_documents=[_make_doc()],
        )
        assert result.output_path is None

    def test_validation_warnings_defaults_to_empty(self) -> None:
        result = KBGenerationResult(
            kb_text="# KB",
            source_documents=[_make_doc()],
        )
        assert result.validation_warnings == []

    def test_output_path_is_preserved(self) -> None:
        result = KBGenerationResult(
            kb_text="# KB",
            source_documents=[_make_doc()],
            output_path=Path("/tmp/output.md"),
        )
        assert result.output_path == Path("/tmp/output.md")

    def test_validation_warnings_are_preserved(self) -> None:
        warnings = ["Missing section: Education", "KB is short"]
        result = KBGenerationResult(
            kb_text="# KB",
            source_documents=[_make_doc()],
            validation_warnings=warnings,
        )
        assert result.validation_warnings == warnings

    def test_multiple_source_documents(self) -> None:
        docs = [_make_doc("a.txt", "aaa"), _make_doc("b.pdf", "bbb")]
        result = KBGenerationResult(
            kb_text="# KB",
            source_documents=docs,
        )
        assert len(result.source_documents) == 2

    def test_model_dump_includes_all_fields(self) -> None:
        result = KBGenerationResult(
            kb_text="# KB",
            source_documents=[_make_doc()],
            output_path=Path("/tmp/out.md"),
            validation_warnings=["warn"],
        )
        data = result.model_dump()
        assert set(data.keys()) == {
            "kb_text",
            "source_documents",
            "output_path",
            "validation_warnings",
        }


class TestKBGenerationResultInvalid:
    """Tests for invalid KBGenerationResult creation."""

    def test_missing_kb_text_raises(self) -> None:
        with pytest.raises(ValidationError):
            KBGenerationResult(  # type: ignore[call-arg]
                source_documents=[_make_doc()],
            )

    def test_missing_source_documents_raises(self) -> None:
        with pytest.raises(ValidationError):
            KBGenerationResult(  # type: ignore[call-arg]
                kb_text="# KB",
            )
