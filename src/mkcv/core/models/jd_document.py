"""Parsed JD document with optional frontmatter."""

from pathlib import Path

from pydantic import BaseModel, field_validator

from mkcv.core.models.jd_frontmatter import JDFrontmatter


class JDDocument(BaseModel):
    """A job description document with optional structured metadata.

    Represents the result of parsing a JD file that may contain
    YAML frontmatter (jd.md) or be plain text (jd.txt).
    """

    metadata: JDFrontmatter | None = None
    body: str
    source_path: Path | None = None

    @field_validator("body", mode="before")
    @classmethod
    def _body_must_not_be_empty(cls, v: str) -> str:
        """Reject empty or whitespace-only body text."""
        if not isinstance(v, str) or not v.strip():
            msg = "body must not be empty"
            raise ValueError(msg)
        return v
