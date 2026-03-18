"""Resume CV content model for RenderCV."""

from pydantic import BaseModel, Field

from mkcv.core.models.social_network import SocialNetwork


class ResumeCV(BaseModel):
    """Resume content matching RenderCV cv section schema."""

    name: str
    location: str
    email: str
    phone: str
    website: str | None = None
    social_networks: list[SocialNetwork] = Field(default_factory=list)
    summary: str = Field(
        max_length=300,
        description="Mission statement rendered at top of resume",
    )
    sections: dict[str, list[dict[str, object]]] = Field(
        description="Flexible sections matching RenderCV schema",
    )
