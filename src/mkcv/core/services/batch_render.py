"""Batch rendering service for multi-theme resume rendering."""

import logging
from pathlib import Path

from mkcv.core.exceptions.render import RenderError
from mkcv.core.models.batch_render_result import (
    BatchRenderResult,
    ThemeRenderResult,
)
from mkcv.core.services.render import RenderService
from mkcv.core.services.yaml_postprocessor import YamlPostProcessor

logger = logging.getLogger(__name__)


class BatchRenderService:
    """Renders a resume across multiple themes.

    Composes RenderService and YamlPostProcessor to iterate over
    a list of themes, injecting each theme into the YAML and
    rendering to an isolated subdirectory.
    """

    def __init__(
        self,
        render_service: RenderService,
        postprocessor: YamlPostProcessor,
    ) -> None:
        self._render_service = render_service
        self._postprocessor = postprocessor

    def render_multi_theme(
        self,
        yaml_path: Path,
        output_dir: Path,
        themes: list[str],
        *,
        formats: list[str] | None = None,
    ) -> BatchRenderResult:
        """Render a resume YAML across multiple themes.

        Each theme's output is placed in output_dir/renders/<theme>/.
        The source YAML is read once and a theme-injected variant is
        written to each subdirectory before rendering.

        Per-theme rendering errors are caught and recorded; remaining
        themes continue rendering.

        Args:
            yaml_path: Path to the source RenderCV YAML file.
            output_dir: Base output directory.
            themes: List of validated theme names.
            formats: Output formats (e.g. ["pdf", "png"]).

        Returns:
            BatchRenderResult with per-theme outcomes.

        Raises:
            RenderError: If the source YAML file cannot be read.
        """
        resolved_yaml = yaml_path.resolve()
        if not resolved_yaml.is_file():
            raise RenderError(f"YAML file not found: {resolved_yaml}")

        try:
            yaml_str = resolved_yaml.read_text(encoding="utf-8")
        except OSError as exc:
            raise RenderError(f"Failed to read YAML file: {resolved_yaml}") from exc

        results: list[ThemeRenderResult] = []

        for theme in themes:
            result = self._render_single_theme(
                yaml_str=yaml_str,
                source_filename=resolved_yaml.name,
                output_dir=output_dir,
                theme=theme,
                formats=formats,
            )
            results.append(result)

        return BatchRenderResult(results=results)

    def _render_single_theme(
        self,
        *,
        yaml_str: str,
        source_filename: str,
        output_dir: Path,
        theme: str,
        formats: list[str] | None,
    ) -> ThemeRenderResult:
        """Render a single theme, catching errors.

        Args:
            yaml_str: Source YAML content.
            source_filename: Original YAML filename (for the variant).
            output_dir: Base output directory.
            theme: Theme name to inject.
            formats: Output formats.

        Returns:
            ThemeRenderResult with success or error status.
        """
        theme_dir = output_dir / "renders" / theme
        try:
            theme_dir.mkdir(parents=True, exist_ok=True)

            # Inject theme into YAML
            themed_yaml = self._postprocessor.inject_theme(yaml_str, theme)

            # Write variant to theme subdirectory
            variant_path = theme_dir / source_filename
            variant_path.write_text(themed_yaml, encoding="utf-8")

            # Render
            logger.info("Rendering theme '%s' to %s", theme, theme_dir)
            output = self._render_service.render_resume(
                variant_path,
                theme_dir,
                theme=theme,
                formats=formats,
            )

            return ThemeRenderResult(
                theme=theme,
                status="success",
                output=output,
            )

        except (RenderError, ValueError, OSError) as exc:
            logger.warning("Failed to render theme '%s': %s", theme, exc, exc_info=True)
            return ThemeRenderResult(
                theme=theme,
                status="error",
                error_message=str(exc),
            )
