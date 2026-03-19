"""Knowledge base validation result model."""

from pydantic import BaseModel


class KBValidationResult(BaseModel):
    """Result of validating a knowledge base Markdown file.

    Attributes:
        is_valid: True if no errors were found (warnings are OK).
        warnings: Non-blocking issues the user should address.
        errors: Blocking issues that prevent generation.
        sections_found: Headings detected in the KB.
        sections_missing: Expected headings not found.
    """

    is_valid: bool
    warnings: list[str]
    errors: list[str]
    sections_found: list[str]
    sections_missing: list[str]
