"""Resume design/theme configuration model."""

from pydantic import BaseModel, Field, field_validator

VALID_PAGE_SIZES = ("letterpaper", "a4paper", "us-letter", "a4")

# Mapping from mkcv page_size names to RenderCV page_size names
PAGE_SIZE_MAP: dict[str, str] = {
    "letterpaper": "us-letter",
    "a4paper": "a4",
    "us-letter": "us-letter",
    "a4": "a4",
}


class ResumeDesign(BaseModel):
    """Design settings for resume rendering.

    Carries theme selection and visual overrides through the pipeline.
    Used by YamlPostProcessor to inject the design section into
    generated YAML.
    """

    theme: str = "sb2nov"
    font: str = "SourceSansPro"
    font_size: str = "10pt"
    page_size: str = "letterpaper"
    colors: dict[str, str] = Field(default_factory=lambda: {"primary": "003366"})

    @field_validator("page_size")
    @classmethod
    def validate_page_size(cls, v: str) -> str:
        """Validate page_size against supported values."""
        if v not in VALID_PAGE_SIZES:
            raise ValueError(
                f"Invalid page_size '{v}'. Supported: {', '.join(VALID_PAGE_SIZES)}"
            )
        return v

    def has_overrides(self) -> bool:
        """Check if any non-default overrides are set."""
        default = ResumeDesign.model_construct(
            theme="sb2nov",
            font="SourceSansPro",
            font_size="10pt",
            page_size="letterpaper",
            colors={"primary": "003366"},
        )
        return (
            self.font != default.font
            or self.font_size != default.font_size
            or self.page_size != default.page_size
            or self.colors != default.colors
        )
