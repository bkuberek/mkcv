"""ATS compliance check model."""

from pydantic import BaseModel


class ATSCheck(BaseModel):
    """ATS compliance verification results."""

    single_column: bool
    no_tables: bool
    no_text_boxes: bool
    standard_headings: bool
    contact_in_body: bool
    standard_bullets: bool
    standard_fonts: bool
    text_extractable: bool
    reading_order_correct: bool
    overall_pass: bool
    issues: list[str]
