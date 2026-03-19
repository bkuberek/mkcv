"""Port interface for extracting text from PDF files."""

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class PdfReaderPort(Protocol):
    """Interface for reading text content from PDF files.

    Implementations: PyPdfReader.
    """

    def extract_text(self, path: Path) -> str:
        """Extract all text content from a PDF file.

        Args:
            path: Path to the PDF file.

        Returns:
            Extracted text content.

        Raises:
            ValidationError: If the PDF cannot be read or is corrupted.
        """
        ...
