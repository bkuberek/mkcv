"""Multi-format document reader adapter."""

import logging
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from mkcv.core.exceptions.kb_generation import DocumentReadError
from mkcv.core.models.document_content import DocumentContent

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Extension → format mapping
# ---------------------------------------------------------------------------

_EXTENSION_FORMAT: dict[str, str] = {
    ".pdf": "pdf",
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".text": "text",
    ".docx": "docx",
    ".html": "html",
    ".htm": "html",
}


class MultiFormatDocumentReader:
    """Reads text content from PDF, Markdown, plain-text, DOCX, and HTML files.

    Implements DocumentReaderPort for use in KBGenerationService.
    """

    # ------------------------------------------------------------------
    # Public interface (DocumentReaderPort)
    # ------------------------------------------------------------------

    def read_file(self, path: Path) -> DocumentContent:
        """Read text content from a single document file.

        Args:
            path: Path to the document file.

        Returns:
            Extracted document content with metadata.

        Raises:
            DocumentReadError: If the file cannot be read or the format
                is unsupported.
        """
        if not path.is_file():
            raise DocumentReadError(f"File not found: {path}")

        ext = path.suffix.lower()
        fmt = _EXTENSION_FORMAT.get(ext)
        if fmt is None:
            raise DocumentReadError(
                f"Unsupported file format '{ext}' for '{path.name}'. "
                f"Supported: {', '.join(sorted(self.supported_extensions()))}"
            )

        dispatch: dict[str, Callable[[Path], tuple[str, dict[str, str]]]] = {
            "pdf": self._read_pdf,
            "markdown": self._read_markdown,
            "text": self._read_text,
            "docx": self._read_docx,
            "html": self._read_html,
        }

        reader = dispatch[fmt]
        text, metadata = reader(path)

        return DocumentContent(
            text=text,
            source_path=path,
            format=fmt,
            char_count=len(text),
            metadata=metadata,
        )

    def supported_extensions(self) -> set[str]:
        """Return the set of file extensions this reader supports.

        Returns:
            Set of lowercase extensions including the dot,
            e.g. ``{".pdf", ".md", ".txt", ".docx", ".html"}``.
        """
        return set(_EXTENSION_FORMAT.keys())

    # ------------------------------------------------------------------
    # Directory scanning
    # ------------------------------------------------------------------

    def read_sources(
        self,
        paths: list[Path],
        *,
        glob: str = "**/*",
    ) -> list[DocumentContent]:
        """Resolve *paths* (files or directories) and read all supported documents.

        Args:
            paths: Files and/or directories to read.
            glob: Glob pattern applied when scanning directories.
                  Defaults to ``**/*`` (recursive, all files).

        Returns:
            List of ``DocumentContent`` in sorted order (by source path).

        Raises:
            DocumentReadError: Propagated from individual file reads.
        """
        discovered: set[Path] = set()
        supported = self.supported_extensions()

        for p in paths:
            resolved = p.resolve()
            if resolved.is_file():
                if resolved.suffix.lower() in supported:
                    discovered.add(resolved)
                else:
                    logger.debug(
                        "Skipping unsupported file: %s",
                        resolved,
                    )
            elif resolved.is_dir():
                for child in resolved.glob(glob):
                    if child.is_file() and child.suffix.lower() in supported:
                        discovered.add(child)
            else:
                logger.warning("Path does not exist, skipping: %s", resolved)

        results: list[DocumentContent] = []
        for file_path in sorted(discovered):
            logger.info("Reading %s", file_path)
            results.append(self.read_file(file_path))

        return results

    # ------------------------------------------------------------------
    # Private format readers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_pdf(path: Path) -> tuple[str, dict[str, str]]:
        """Extract text from a PDF using *pypdf*."""
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError

        try:
            reader = PdfReader(path)
        except PdfReadError as exc:
            raise DocumentReadError(
                f"Cannot read PDF '{path.name}': file is corrupted or not a valid PDF."
            ) from exc

        metadata: dict[str, str] = {}
        if reader.metadata:
            if reader.metadata.title:
                metadata["title"] = reader.metadata.title
            if reader.metadata.author:
                metadata["author"] = reader.metadata.author

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

        text = "\n".join(pages)

        if not text.strip():
            warnings.warn(
                f"PDF '{path.name}' appears to be image-only; "
                "no extractable text was found.",
                stacklevel=2,
            )

        return text, metadata

    @staticmethod
    def _read_markdown(path: Path) -> tuple[str, dict[str, str]]:
        """Read a Markdown file as plain text."""
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise DocumentReadError(
                f"Cannot read Markdown file '{path.name}': {exc}"
            ) from exc
        return text, {}

    @staticmethod
    def _read_text(path: Path) -> tuple[str, dict[str, str]]:
        """Read a plain-text file."""
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise DocumentReadError(
                f"Cannot read text file '{path.name}': {exc}"
            ) from exc
        return text, {}

    @staticmethod
    def _read_docx(path: Path) -> tuple[str, dict[str, str]]:
        """Extract text from a DOCX file using *python-docx*."""
        import docx as python_docx

        try:
            doc = python_docx.Document(str(path))
        except Exception as exc:
            raise DocumentReadError(
                f"Cannot read DOCX file '{path.name}': {exc}"
            ) from exc

        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)

        metadata: dict[str, str] = {}
        core = doc.core_properties
        if core.title:
            metadata["title"] = core.title
        if core.author:
            metadata["author"] = core.author

        return text, metadata

    @staticmethod
    def _read_html(path: Path) -> tuple[str, dict[str, str]]:
        """Extract text from an HTML file using *beautifulsoup4* + *html2text*."""
        import html2text
        from bs4 import BeautifulSoup

        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise DocumentReadError(
                f"Cannot read HTML file '{path.name}': {exc}"
            ) from exc

        soup = BeautifulSoup(raw, "html.parser")

        metadata: dict[str, str] = {}
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            metadata["title"] = title_tag.string.strip()

        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.ignore_images = True
        converter.body_width = 0  # no wrapping
        text: str = converter.handle(raw)

        return text, metadata
