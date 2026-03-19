"""Tests for PyPdfReader adapter."""

from pathlib import Path

import pytest
from pypdf import PdfWriter

from mkcv.adapters.filesystem.pdf_reader import PyPdfReader
from mkcv.core.exceptions.validation import ValidationError


@pytest.fixture
def reader() -> PyPdfReader:
    """Create a PyPdfReader instance."""
    return PyPdfReader()


@pytest.fixture
def simple_pdf(tmp_path: Path) -> Path:
    """Create a minimal PDF with extractable text."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)

    # Add text via annotation (simplest way to add extractable text
    # without needing reportlab or similar)
    from pypdf.generic import (
        ArrayObject,
        DictionaryObject,
        NameObject,
        TextStringObject,
    )

    page = writer.pages[0]

    # Build a simple FreeText annotation with content
    annotation = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Annot"),
            NameObject("/Subtype"): NameObject("/FreeText"),
            NameObject("/Contents"): TextStringObject("John Doe - Software Engineer"),
            NameObject("/Rect"): ArrayObject(
                [
                    TextStringObject("50"),
                    TextStringObject("700"),
                    TextStringObject("400"),
                    TextStringObject("750"),
                ]
            ),
        }
    )

    if "/Annots" not in page:
        page[NameObject("/Annots")] = ArrayObject()
    page[NameObject("/Annots")].append(annotation)  # type: ignore[union-attr]

    path = tmp_path / "resume.pdf"
    with open(path, "wb") as f:
        writer.write(f)

    return path


@pytest.fixture
def empty_pdf(tmp_path: Path) -> Path:
    """Create a valid PDF with no text content."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)

    path = tmp_path / "empty.pdf"
    with open(path, "wb") as f:
        writer.write(f)

    return path


@pytest.fixture
def corrupt_pdf(tmp_path: Path) -> Path:
    """Create a corrupt PDF file."""
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"NOT-A-VALID-PDF-CONTENT-AT-ALL")
    return path


class TestExtractTextFromValidPdf:
    """Tests for extracting text from valid PDFs."""

    def test_returns_string(self, reader: PyPdfReader, simple_pdf: Path) -> None:
        result = reader.extract_text(simple_pdf)
        assert isinstance(result, str)

    def test_empty_pdf_returns_string(
        self, reader: PyPdfReader, empty_pdf: Path
    ) -> None:
        result = reader.extract_text(empty_pdf)
        assert isinstance(result, str)


class TestExtractTextFromCorruptPdf:
    """Tests for handling corrupt PDF files."""

    def test_corrupt_pdf_raises_validation_error(
        self, reader: PyPdfReader, corrupt_pdf: Path
    ) -> None:
        with pytest.raises(ValidationError, match="corrupted"):
            reader.extract_text(corrupt_pdf)


class TestExtractTextFromMissingFile:
    """Tests for handling missing files."""

    def test_missing_file_raises_file_not_found(
        self, reader: PyPdfReader, tmp_path: Path
    ) -> None:
        missing = tmp_path / "nonexistent.pdf"
        with pytest.raises(FileNotFoundError, match="not found"):
            reader.extract_text(missing)


class TestPdfReaderProtocolConformance:
    """Verify PyPdfReader satisfies PdfReaderPort."""

    def test_implements_protocol(self) -> None:
        from mkcv.core.ports.pdf_reader import PdfReaderPort

        reader = PyPdfReader()
        assert isinstance(reader, PdfReaderPort)
