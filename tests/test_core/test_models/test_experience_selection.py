"""Tests for ExperienceSelection model."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.experience_selection import ExperienceSelection
from mkcv.core.models.selected_experience import SelectedExperience


def _make_selected_experience(company: str = "Acme Corp") -> SelectedExperience:
    return SelectedExperience(
        company=company,
        role="Staff Engineer",
        period="2020-2024",
        relevance_score=85,
        match_reasons=["Python expertise", "Team leadership"],
        suggested_bullets=["Led platform migration"],
        bullets_to_drop=["Fixed minor UI bugs"],
        reframe_suggestion="Focus on technical leadership angle",
    )


class TestExperienceSelection:
    """Tests for ExperienceSelection model."""

    def test_valid_creation(self) -> None:
        selection = ExperienceSelection(
            selected_experiences=[_make_selected_experience()],
            skills_to_highlight=["Python", "Kubernetes"],
            skills_to_omit=["jQuery"],
            gap_analysis="Missing cloud certification experience",
            mission_themes=["Technical leadership", "Platform engineering"],
        )
        assert len(selection.selected_experiences) == 1

    def test_skills_to_highlight(self) -> None:
        selection = ExperienceSelection(
            selected_experiences=[],
            skills_to_highlight=["Python", "Go", "Kubernetes"],
            skills_to_omit=[],
            gap_analysis="No gaps identified",
            mission_themes=[],
        )
        assert selection.skills_to_highlight == ["Python", "Go", "Kubernetes"]

    def test_skills_to_omit(self) -> None:
        selection = ExperienceSelection(
            selected_experiences=[],
            skills_to_highlight=[],
            skills_to_omit=["jQuery", "PHP"],
            gap_analysis="No gaps identified",
            mission_themes=[],
        )
        assert selection.skills_to_omit == ["jQuery", "PHP"]

    def test_gap_analysis_value(self) -> None:
        selection = ExperienceSelection(
            selected_experiences=[],
            skills_to_highlight=[],
            skills_to_omit=[],
            gap_analysis="Lacks ML/AI experience mentioned in JD",
            mission_themes=[],
        )
        assert selection.gap_analysis == "Lacks ML/AI experience mentioned in JD"

    def test_mission_themes(self) -> None:
        themes = ["Innovation", "Scale"]
        selection = ExperienceSelection(
            selected_experiences=[],
            skills_to_highlight=[],
            skills_to_omit=[],
            gap_analysis="None",
            mission_themes=themes,
        )
        assert selection.mission_themes == themes

    def test_empty_experiences_allowed(self) -> None:
        selection = ExperienceSelection(
            selected_experiences=[],
            skills_to_highlight=[],
            skills_to_omit=[],
            gap_analysis="All gaps",
            mission_themes=[],
        )
        assert selection.selected_experiences == []

    def test_multiple_experiences(self) -> None:
        experiences = [
            _make_selected_experience("Acme Corp"),
            _make_selected_experience("Startup X"),
        ]
        selection = ExperienceSelection(
            selected_experiences=experiences,
            skills_to_highlight=["Python"],
            skills_to_omit=[],
            gap_analysis="No gaps",
            mission_themes=["Engineering"],
        )
        assert len(selection.selected_experiences) == 2

    def test_gap_analysis_required(self) -> None:
        with pytest.raises(ValidationError):
            ExperienceSelection(
                selected_experiences=[],  # type: ignore[call-arg]
                skills_to_highlight=[],
                skills_to_omit=[],
                mission_themes=[],
            )

    def test_model_dump_includes_all_fields(self) -> None:
        selection = ExperienceSelection(
            selected_experiences=[],
            skills_to_highlight=[],
            skills_to_omit=[],
            gap_analysis="No gaps",
            mission_themes=[],
        )
        data = selection.model_dump()
        expected_keys = {
            "selected_experiences",
            "skills_to_highlight",
            "skills_to_omit",
            "gap_analysis",
            "mission_themes",
        }
        assert set(data.keys()) == expected_keys
