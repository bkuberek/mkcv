"""Tests for DocumentContent model."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from mkcv.core.models.document_content import DocumentContent


class TestDocumentContentValid:
    """Tests for valid DocumentContent creation."""

    def test_minimal_valid_instance(self) -> None:
        doc = DocumentContent(
            text="Hello world",
            source_path=Path("/tmp/test.txt"),
            format="text",
            char_count=11,
        )
        assert doc.text == "Hello world"
        assert doc.source_path == Path("/tmp/test.txt")
        assert doc.format == "text"
        assert doc.char_count == 11

    def test_metadata_defaults_to_empty_dict(self) -> None:
        doc = DocumentContent(
            text="content",
            source_path=Path("/tmp/file.md"),
            format="markdown",
            char_count=7,
        )
        assert doc.metadata == {}

    def test_metadata_is_preserved(self) -> None:
        meta = {"title": "My Resume", "author": "Jane Doe"}
        doc = DocumentContent(
            text="content",
            source_path=Path("/tmp/file.pdf"),
            format="pdf",
            char_count=7,
            metadata=meta,
        )
        assert doc.metadata == meta

    def test_char_count_zero_is_valid(self) -> None:
        doc = DocumentContent(
            text="",
            source_path=Path("/tmp/empty.txt"),
            format="text",
            char_count=0,
        )
        assert doc.char_count == 0

    def test_model_dump_includes_all_fields(self) -> None:
        doc = DocumentContent(
            text="test",
            source_path=Path("/tmp/test.txt"),
            format="text",
            char_count=4,
            metadata={"key": "value"},
        )
        data = doc.model_dump()
        assert set(data.keys()) == {
            "text",
            "source_path",
            "format",
            "char_count",
            "metadata",
        }


class TestDocumentContentInvalid:
    """Tests for invalid DocumentContent creation."""

    def test_negative_char_count_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocumentContent(
                text="hello",
                source_path=Path("/tmp/test.txt"),
                format="text",
                char_count=-1,
            )

    def test_missing_text_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocumentContent(  # type: ignore[call-arg]
                source_path=Path("/tmp/test.txt"),
                format="text",
                char_count=0,
            )

    def test_missing_source_path_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocumentContent(  # type: ignore[call-arg]
                text="hello",
                format="text",
                char_count=5,
            )

    def test_missing_format_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocumentContent(  # type: ignore[call-arg]
                text="hello",
                source_path=Path("/tmp/test.txt"),
                char_count=5,
            )

    def test_missing_char_count_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocumentContent(  # type: ignore[call-arg]
                text="hello",
                source_path=Path("/tmp/test.txt"),
                format="text",
            )
