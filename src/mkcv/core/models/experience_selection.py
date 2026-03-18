"""Experience selection output model (Stage 2)."""

from pydantic import BaseModel, Field

from mkcv.core.models.selected_experience import SelectedExperience


class ExperienceSelection(BaseModel):
    """Complete experience selection result (Stage 2 output)."""

    selected_experiences: list[SelectedExperience]
    skills_to_highlight: list[str]
    skills_to_omit: list[str]
    gap_analysis: str = Field(description="What the candidate is missing vs the JD")
    mission_themes: list[str] = Field(
        description="Themes to inform the mission statement"
    )
