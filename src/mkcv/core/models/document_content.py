"""Extracted document content model."""

from pathlib import Path

from pydantic import BaseModel, Field


class DocumentContent(BaseModel):
    """Content extracted from a source document.

    Attributes:
        text: The extracted plain-text content.
        source_path: Path to the original file.
        format: File format identifier, e.g. "pdf", "markdown", "docx".
        char_count: Number of characters in the extracted text.
        metadata: Optional key-value metadata from the document.
    """

    text: str
    source_path: Path
    format: str
    char_count: int = Field(ge=0)
    metadata: dict[str, str] = Field(default_factory=dict)
