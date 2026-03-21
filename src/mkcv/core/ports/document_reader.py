"""Port interface for reading text from multi-format documents."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from mkcv.core.models.document_content import DocumentContent


@runtime_checkable
class DocumentReaderPort(Protocol):
    """Interface for reading text content from various document formats.

    Implementations: MultiFormatDocumentReader.
    """

    def read_file(self, path: Path) -> DocumentContent:
        """Read text content from a single document file.

        Args:
            path: Path to the document file.

        Returns:
            Extracted document content with metadata.

        Raises:
            DocumentReadError: If the file cannot be read or parsed.
        """
        ...

    def supported_extensions(self) -> set[str]:
        """Return the set of file extensions this reader supports.

        Returns:
            Set of lowercase extensions including the dot, e.g. {".pdf", ".md"}.
        """
        ...
