"""PDF text extraction adapter using pypdf."""

import logging
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from mkcv.core.exceptions.validation import ValidationError

logger = logging.getLogger(__name__)


class PyPdfReader:
    """Extracts text from PDF files using pypdf.

    Implements PdfReaderPort for use in ValidationService.
    """

    def extract_text(self, path: Path) -> str:
        """Extract all text content from a PDF file.

        Concatenates text from all pages, separated by newlines.

        Args:
            path: Path to the PDF file.

        Returns:
            Extracted text content. May be empty for image-only PDFs.

        Raises:
            ValidationError: If the PDF is corrupted or cannot be read.
            FileNotFoundError: If the file does not exist.
        """
        if not path.is_file():
            raise FileNotFoundError(f"PDF file not found: {path}")

        try:
            reader = PdfReader(path)
        except PdfReadError as exc:
            raise ValidationError(
                f"Cannot read PDF '{path.name}': file is corrupted or not a valid PDF."
            ) from exc

        pages: list[str] = []
        for page_num, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except PdfReadError as exc:
                logger.warning(
                    "Failed to extract text from page %d of '%s': %s",
                    page_num,
                    path.name,
                    exc,
                )
                continue
            pages.append(text)

        return "\n".join(pages)
