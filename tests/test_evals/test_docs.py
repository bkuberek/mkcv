"""Tests for the eval harness documentation and the publishing folder (REQ-EV-22)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = (ROOT / "evals" / "README.md").read_text(encoding="utf-8")
MODELS = (ROOT / "docs" / "models.md").read_text(encoding="utf-8")
DEVELOPMENT = (ROOT / "docs" / "DEVELOPMENT.md").read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """The section's text with line breaks collapsed to single spaces."""
    start = text.index(f"## {heading}")
    following = text.find("\n## ", start + 1)
    body = text[start:] if following == -1 else text[start:following]
    return " ".join(body.split())


class TestEvalsReadme:
    def test_it_lists_the_keys_to_export_for_each_provider(self) -> None:
        for variable in (
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
        ):
            assert variable in README

    def test_it_explains_bootstrapping_and_reviewing_the_references(self) -> None:
        assert "bootstrap-reference" in README
        assert re.search(r"review", README, re.IGNORECASE)
        assert "evals/fixtures/reference" in README

    def test_it_gives_the_one_command_run(self) -> None:
        assert "uv run python -m evals run --yes" in README

    def test_it_points_to_the_cost_estimate(self) -> None:
        assert "uv run python -m evals estimate" in README

    def test_it_explains_how_to_read_the_report(self) -> None:
        for heading in ("Eligible", "Recommendations", "Suggested profile changes"):
            assert heading in README

    def test_it_explains_publishing(self) -> None:
        assert "report" in README
        assert "--publish" in README
        assert "evals/results/published" in README

    def test_it_explains_how_to_apply_the_results(self) -> None:
        assert "core/catalog/builtin_model_profiles.py" in README
        assert "docs/models.md" in README
        assert 'evidence="eval"' in README

    def test_it_explains_the_tournament_batching_and_caching(self) -> None:
        for term in (
            "--round",
            "--resume",
            "--no-batch",
            "[caching]",
            "check-reference",
        ):
            assert term in README

    def test_it_says_the_judge_needs_a_key_too(self) -> None:
        assert "judge" in README.lower()
        assert "self-judged" in README


class TestModelsDoc:
    def test_it_has_the_how_recommendations_are_made_section(self) -> None:
        assert "## How recommendations are made" in MODELS

    def test_the_section_links_the_evals_readme(self) -> None:
        assert "evals/README.md" in _section(MODELS, "How recommendations are made")

    def test_the_section_states_that_all_profiles_are_provisional(self) -> None:
        section = _section(MODELS, "How recommendations are made")
        assert "provisional" in section

    def test_the_section_states_the_quality_first_rule(self) -> None:
        section = _section(MODELS, "How recommendations are made")
        assert "highest primary quality score" in section
        assert "within 0.01" in section

    def test_the_section_explains_the_judge_panel_and_self_preference(
        self,
    ) -> None:
        section = _section(MODELS, "How recommendations are made")
        assert "judge panel" in section
        assert "self-judged" in section
        assert "too close to call" in section

    def test_the_planned_harness_wording_is_gone(self) -> None:
        assert "is planned" not in MODELS

    def test_the_intro_link_points_at_the_new_section(self) -> None:
        assert "(#how-recommendations-are-made)" in MODELS
        assert "(#evidence)" not in MODELS


class TestDevelopmentGuide:
    def test_it_points_to_the_evals_readme(self) -> None:
        assert "evals/README.md" in DEVELOPMENT


class TestPublishedFolder:
    def test_the_published_folder_is_kept_in_git(self) -> None:
        assert (ROOT / "evals" / "results" / "published" / ".gitkeep").is_file()
