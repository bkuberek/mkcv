"""Tests for YamlPostProcessor."""

import pytest

from mkcv.core.models.resume_design import ResumeDesign
from mkcv.core.services.yaml_postprocessor import YamlPostProcessor


@pytest.fixture
def postprocessor() -> YamlPostProcessor:
    """Create a YamlPostProcessor instance."""
    return YamlPostProcessor()


SAMPLE_YAML = """\
cv:
  name: John Doe
  sections:
    summary:
      - Software engineer with testing experience.
design:
  theme: sb2nov
"""

SAMPLE_YAML_NO_DESIGN = """\
cv:
  name: John Doe
  sections:
    summary:
      - Software engineer with testing experience.
"""

SAMPLE_YAML_WITH_FONT = """\
cv:
  name: John Doe
design:
  theme: sb2nov
  font: Charter
  page_size: letterpaper
"""


class TestInjectTheme:
    """Tests for inject_theme method."""

    def test_replaces_existing_theme(self, postprocessor: YamlPostProcessor) -> None:
        result = postprocessor.inject_theme(SAMPLE_YAML, "classic")
        assert "theme: classic" in result

    def test_adds_missing_design_section(
        self, postprocessor: YamlPostProcessor
    ) -> None:
        result = postprocessor.inject_theme(SAMPLE_YAML_NO_DESIGN, "moderncv")
        assert "theme: moderncv" in result
        assert "design:" in result

    def test_preserves_cv_content(self, postprocessor: YamlPostProcessor) -> None:
        result = postprocessor.inject_theme(SAMPLE_YAML, "classic")
        assert "John Doe" in result
        assert "Software engineer" in result

    def test_preserves_other_design_keys(
        self, postprocessor: YamlPostProcessor
    ) -> None:
        result = postprocessor.inject_theme(SAMPLE_YAML_WITH_FONT, "classic")
        assert "theme: classic" in result
        assert "font: Charter" in result
        assert "page_size: letterpaper" in result

    def test_handles_correct_theme_no_op(
        self, postprocessor: YamlPostProcessor
    ) -> None:
        result = postprocessor.inject_theme(SAMPLE_YAML, "sb2nov")
        assert "theme: sb2nov" in result


class TestInjectDesign:
    """Tests for inject_design method."""

    def test_sets_theme_only_when_no_overrides(
        self, postprocessor: YamlPostProcessor
    ) -> None:
        design = ResumeDesign(theme="classic")
        result = postprocessor.inject_design(SAMPLE_YAML, design)
        assert "theme: classic" in result

    def test_sets_font_override(self, postprocessor: YamlPostProcessor) -> None:
        design = ResumeDesign(theme="classic", font="Charter")
        result = postprocessor.inject_design(SAMPLE_YAML, design)
        assert "theme: classic" in result
        assert "font: Charter" in result

    def test_sets_page_size_with_mapping(
        self, postprocessor: YamlPostProcessor
    ) -> None:
        design = ResumeDesign(theme="classic", page_size="a4paper")
        result = postprocessor.inject_design(SAMPLE_YAML, design)
        assert "page_size: a4" in result

    def test_sets_color_override(self, postprocessor: YamlPostProcessor) -> None:
        design = ResumeDesign(
            theme="classic",
            colors={"primary": "004080"},
        )
        result = postprocessor.inject_design(SAMPLE_YAML, design)
        assert (
            "color: '004080'" in result
            or 'color: "004080"' in result
            or "color: 004080" in result
        )

    def test_handles_multiline_yaml(self, postprocessor: YamlPostProcessor) -> None:
        yaml_str = """\
cv:
  name: John Doe
  sections:
    summary:
      - Line one.
      - Line two.
    experience:
      - company: Acme
        position: Engineer
design:
  theme: sb2nov
"""
        design = ResumeDesign(theme="engineeringresumes")
        result = postprocessor.inject_design(yaml_str, design)
        assert "theme: engineeringresumes" in result
        assert "John Doe" in result
        assert "Acme" in result


class TestEdgeCases:
    """Tests for edge cases."""

    def test_invalid_yaml_raises_value_error(
        self, postprocessor: YamlPostProcessor
    ) -> None:
        with pytest.raises(ValueError, match="Empty or invalid YAML"):
            postprocessor.inject_theme("", "classic")

    def test_empty_yaml_raises_value_error(
        self, postprocessor: YamlPostProcessor
    ) -> None:
        with pytest.raises(ValueError, match="Empty or invalid YAML"):
            postprocessor.inject_design("", ResumeDesign())

    def test_whitespace_only_yaml_raises_value_error(
        self, postprocessor: YamlPostProcessor
    ) -> None:
        with pytest.raises(ValueError, match="Empty or invalid YAML"):
            postprocessor.inject_theme("   \n  \n  ", "classic")
