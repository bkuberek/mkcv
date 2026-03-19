"""Cover letter design/layout configuration model."""

from pydantic import BaseModel, field_validator

from mkcv.core.models.validators import validate_dimension

PLACEHOLDER_COMPANY_BLOCKLIST: frozenset[str] = frozenset(
    {
        "",
        "company",
        "company name",
        "the company",
        "your company",
        "employer",
        "hiring company",
        "organization",
        "unknown",
        "n/a",
        "tbd",
        "general purpose resume",
        "general purpose",
    }
)


class CoverLetterDesign(BaseModel):
    """Design settings for cover letter PDF rendering.

    Controls Typst template parameters: page layout, typography,
    and addressing preferences.
    """

    # Page layout
    page_size: str = "us-letter"
    margin_top: str = "1.2in"
    margin_bottom: str = "1in"
    margin_left: str = "1in"
    margin_right: str = "1in"

    # Typography
    font: str = "Source Sans Pro"
    font_size: str = "11pt"
    line_spacing: str = "0.7em"
    name_size: str = "16pt"

    # Addressing defaults
    default_salutation: str = "Dear Hiring Manager,"

    @field_validator(
        "margin_top",
        "margin_bottom",
        "margin_left",
        "margin_right",
        "font_size",
        "line_spacing",
        "name_size",
        mode="before",
    )
    @classmethod
    def check_dimension(cls, v: str) -> str:
        """Validate dimension values match expected pattern."""
        result = validate_dimension(v)
        if result is None:
            raise ValueError("Dimension value cannot be None")
        return result

    @staticmethod
    def is_placeholder_company(name: str) -> bool:
        """Check whether a company name is a generic placeholder."""
        return name.strip().lower() in PLACEHOLDER_COMPANY_BLOCKLIST

    @classmethod
    def resolve_salutation(
        cls,
        *,
        salutation: str | None = None,
        company: str | None = None,
        default: str = "Dear Hiring Manager,",
    ) -> str:
        """Determine the best salutation from available information.

        Uses the LLM-generated salutation if non-empty.
        Falls back to company-based greeting, then generic default.
        """
        if salutation and salutation.strip():
            return salutation

        if company and company.strip() and not cls.is_placeholder_company(company):
            return f"Dear {company.strip()} Hiring Team,"

        return default
