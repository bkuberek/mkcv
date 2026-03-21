"""Knowledge base generation result model."""

from pathlib import Path

from pydantic import BaseModel, Field

from mkcv.core.models.document_content import DocumentContent


class KBGenerationResult(BaseModel):
    """Result of generating a knowledge base from source documents.

    Attributes:
        kb_text: The generated knowledge base Markdown content.
        source_documents: Documents that were used as input.
        output_path: Path where the KB file was written, if applicable.
        validation_warnings: Non-blocking issues found during validation.
    """

    kb_text: str
    source_documents: list[DocumentContent]
    output_path: Path | None = None
    validation_warnings: list[str] = Field(default_factory=list)
