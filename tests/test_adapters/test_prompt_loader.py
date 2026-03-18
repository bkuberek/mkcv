"""Tests for FileSystemPromptLoader."""

import pytest

from mkcv.adapters.filesystem.prompt_loader import FileSystemPromptLoader
from mkcv.core.exceptions import TemplateError


class TestFileSystemPromptLoader:
    """Tests for prompt template loading and rendering."""

    def test_lists_bundled_templates(self) -> None:
        loader = FileSystemPromptLoader()
        templates = loader.list_templates()
        assert len(templates) > 0

    def test_bundled_templates_include_analyze_jd(self) -> None:
        loader = FileSystemPromptLoader()
        templates = loader.list_templates()
        assert "analyze_jd.j2" in templates

    def test_renders_template_with_context(self) -> None:
        loader = FileSystemPromptLoader()
        rendered = loader.render(
            "analyze_jd.j2", {"jd_text": "We need a Python engineer."}
        )
        assert "We need a Python engineer." in rendered

    def test_raises_template_error_for_missing_template(self) -> None:
        loader = FileSystemPromptLoader()
        with pytest.raises(TemplateError):
            loader.render("nonexistent_template.j2", {})

    def test_load_raises_template_error_for_missing_template(self) -> None:
        loader = FileSystemPromptLoader()
        with pytest.raises(TemplateError):
            loader.load("nonexistent_template.j2")

    def test_loads_raw_template_source(self) -> None:
        loader = FileSystemPromptLoader()
        source = loader.load("analyze_jd.j2")
        assert "{{ jd_text }}" in source

    def test_render_returns_string(self) -> None:
        loader = FileSystemPromptLoader()
        result = loader.render("analyze_jd.j2", {"jd_text": "Test"})
        assert isinstance(result, str)

    def test_list_templates_returns_sorted_list(self) -> None:
        loader = FileSystemPromptLoader()
        templates = loader.list_templates()
        assert templates == sorted(templates)
