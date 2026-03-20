"""Tests for resume-related models (ExperienceEntry, ResumeDesign, SocialNetwork)."""

import pytest
from pydantic import ValidationError

from mkcv.core.models.experience_entry import ExperienceEntry
from mkcv.core.models.resume_design import ResumeDesign
from mkcv.core.models.social_network import SocialNetwork


class TestExperienceEntry:
    """Tests for ExperienceEntry model."""

    def test_valid_entry(self) -> None:
        entry = ExperienceEntry(
            company="Acme Corp",
            position="Staff Engineer",
            start_date="2020-01",
            end_date="2024-06",
            highlights=["Built platform serving 1M requests/day"],
        )
        assert entry.company == "Acme Corp"

    def test_min_one_highlight_required(self) -> None:
        with pytest.raises(ValidationError):
            ExperienceEntry(
                company="Acme Corp",
                position="Staff Engineer",
                start_date="2020-01",
                end_date="2024-06",
                highlights=[],
            )

    def test_max_ten_highlights(self) -> None:
        with pytest.raises(ValidationError):
            ExperienceEntry(
                company="Acme Corp",
                position="Staff Engineer",
                start_date="2020-01",
                end_date="2024-06",
                highlights=[
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                    "h7",
                    "h8",
                    "h9",
                    "h10",
                    "h11",
                ],
            )

    def test_ten_highlights_allowed(self) -> None:
        entry = ExperienceEntry(
            company="Acme Corp",
            position="Staff Engineer",
            start_date="2020-01",
            end_date="2024-06",
            highlights=[
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "h7",
                "h8",
                "h9",
                "h10",
            ],
        )
        assert len(entry.highlights) == 10

    def test_location_defaults_to_none(self) -> None:
        entry = ExperienceEntry(
            company="Acme Corp",
            position="Staff Engineer",
            start_date="2020-01",
            end_date="2024-06",
            highlights=["Built platform"],
        )
        assert entry.location is None

    def test_location_with_value(self) -> None:
        entry = ExperienceEntry(
            company="Acme Corp",
            position="Staff Engineer",
            location="Remote",
            start_date="2020-01",
            end_date="2024-06",
            highlights=["Built platform"],
        )
        assert entry.location == "Remote"


class TestResumeDesign:
    """Tests for ResumeDesign model."""

    def test_default_theme(self) -> None:
        design = ResumeDesign()
        assert design.theme == "sb2nov"

    def test_default_font(self) -> None:
        design = ResumeDesign()
        assert design.font == "SourceSansPro"

    def test_default_font_size(self) -> None:
        design = ResumeDesign()
        assert design.font_size == "10pt"

    def test_default_page_size(self) -> None:
        design = ResumeDesign()
        assert design.page_size == "letterpaper"

    def test_default_colors(self) -> None:
        design = ResumeDesign()
        assert design.colors == {"primary": "003366"}

    def test_custom_theme(self) -> None:
        design = ResumeDesign(theme="classic")
        assert design.theme == "classic"


class TestSocialNetwork:
    """Tests for SocialNetwork model."""

    def test_valid_linkedin(self) -> None:
        sn = SocialNetwork(network="LinkedIn", username="johndoe")
        assert sn.network == "LinkedIn"

    def test_valid_github(self) -> None:
        sn = SocialNetwork(network="GitHub", username="johndoe")
        assert sn.network == "GitHub"

    def test_valid_twitter(self) -> None:
        sn = SocialNetwork(network="Twitter", username="johndoe")
        assert sn.network == "Twitter"

    def test_valid_website(self) -> None:
        sn = SocialNetwork(network="Website", username="johndoe.dev")
        assert sn.network == "Website"

    def test_invalid_network_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SocialNetwork(
                network="Facebook",  # type: ignore[arg-type]
                username="johndoe",
            )
