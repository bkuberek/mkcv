"""Resume design/theme configuration model."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from mkcv.core.models.entry_layout import EntryLayout
from mkcv.core.models.header_layout import HeaderLayout
from mkcv.core.models.page_layout import PageLayout
from mkcv.core.models.section_title_layout import SectionTitleLayout
from mkcv.core.models.typography_layout import TypographyLayout

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

    Supports both legacy flat fields (font, font_size, page_size, colors)
    and nested sub-models for fine-grained layout control (page, header,
    entries, section_titles, typography).
    """

    theme: str = "sb2nov"

    # Legacy convenience fields (kept for backward compatibility)
    font: str = "SourceSansPro"
    font_size: str = "10pt"
    page_size: str = "letterpaper"
    colors: dict[str, str] = Field(default_factory=lambda: {"primary": "003366"})

    # Nested sub-models for fine-grained layout control
    page: PageLayout | None = None
    header: HeaderLayout | None = None
    entries: EntryLayout | None = None
    section_titles: SectionTitleLayout | None = None
    typography: TypographyLayout | None = None

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
        has_flat = (
            self.font != default.font
            or self.font_size != default.font_size
            or self.page_size != default.page_size
            or self.colors != default.colors
        )
        has_nested = any(
            sub is not None
            for sub in (
                self.page,
                self.header,
                self.entries,
                self.section_titles,
                self.typography,
            )
        )
        return has_flat or has_nested

    def to_rendercv_dict(self) -> dict[str, Any]:
        """Build a RenderCV-compatible design dict.

        Emits the theme always. Emits legacy flat fields (font,
        font_size, color, page_size) only when they differ from
        defaults. Emits nested sub-model sections only when they
        have non-None fields.
        """
        result: dict[str, Any] = {"theme": self.theme}

        defaults = ResumeDesign.model_construct(
            font="SourceSansPro",
            font_size="10pt",
            page_size="letterpaper",
            colors={"primary": "003366"},
        )

        # Legacy flat fields at RenderCV's design top level
        if self.font != defaults.font:
            result["font"] = self.font
        if self.font_size != defaults.font_size:
            result["font_size"] = self.font_size
        if self.page_size != defaults.page_size:
            result["page_size"] = PAGE_SIZE_MAP.get(self.page_size, self.page_size)
        if self.colors.get("primary") != defaults.colors.get("primary"):
            result["color"] = self.colors.get("primary", "003366")

        # Nested sub-model sections (only emit non-None fields)
        if self.page is not None:
            page_dict = self.page.to_rendercv_dict()
            if page_dict:
                result["page"] = page_dict

        if self.header is not None:
            header_dict = self.header.to_rendercv_dict()
            if header_dict:
                result["header"] = header_dict

        if self.entries is not None:
            entries_dict = self.entries.to_rendercv_dict()
            if entries_dict:
                result["entries"] = entries_dict

        if self.section_titles is not None:
            st_dict = self.section_titles.to_rendercv_dict()
            if st_dict:
                result["section_titles"] = st_dict

        if self.typography is not None:
            typo_dict = self.typography.to_rendercv_dict()
            if typo_dict:
                result["typography"] = typo_dict

        return result
