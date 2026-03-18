"""Filesystem-based prompt template loader using Jinja2."""

from importlib import resources
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from mkcv.core.exceptions.template import TemplateError


class FileSystemPromptLoader:
    """Loads and renders Jinja2 prompt templates from the filesystem.

    By default, loads templates bundled with the mkcv package
    (src/mkcv/prompts/). A user-override directory can be specified
    to customize or extend templates.

    Implements: PromptLoaderPort
    """

    def __init__(self, override_dir: Path | None = None) -> None:
        """Initialize the prompt loader.

        Args:
            override_dir: Optional directory with user template overrides.
                          Templates here take precedence over bundled ones.
        """
        search_paths: list[str] = []

        # User overrides take precedence
        if override_dir and override_dir.is_dir():
            search_paths.append(str(override_dir))

        # Bundled templates as fallback
        bundled_path = resources.files("mkcv") / "prompts"
        search_paths.append(str(bundled_path))

        self._env = Environment(
            loader=FileSystemLoader(search_paths),
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def load(self, template_name: str) -> str:
        """Load a raw template string by name.

        Args:
            template_name: Template filename (e.g., 'analyze_jd.j2').

        Returns:
            The raw template source string.

        Raises:
            TemplateError: If the template is not found.
        """
        try:
            source, _, _ = self._env.loader.get_source(self._env, template_name)  # type: ignore[union-attr]
            return source
        except TemplateNotFound as e:
            raise TemplateError(
                f"Prompt template not found: {template_name}",
                template_name=template_name,
            ) from e

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Load a template and render it with the given context.

        Args:
            template_name: Template filename (e.g., 'analyze_jd.j2').
            context: Variables to pass to the template.

        Returns:
            The rendered template string.

        Raises:
            TemplateError: If the template is not found or rendering fails.
        """
        try:
            template = self._env.get_template(template_name)
            return template.render(**context)
        except TemplateNotFound as e:
            raise TemplateError(
                f"Prompt template not found: {template_name}",
                template_name=template_name,
            ) from e
        except Exception as e:
            raise TemplateError(
                f"Error rendering template {template_name}: {e}",
                template_name=template_name,
            ) from e

    def list_templates(self) -> list[str]:
        """List all available template names.

        Returns:
            Sorted list of template filenames.
        """
        return sorted(self._env.list_templates())
