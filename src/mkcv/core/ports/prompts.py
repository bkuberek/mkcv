"""Port interface for loading prompt templates."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PromptLoaderPort(Protocol):
    """Interface for loading and rendering Jinja2 prompt templates.

    Implementations: FileSystemPromptLoader.
    """

    def load(self, template_name: str) -> str:
        """Load a raw template string by name."""
        ...

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Load a template and render it with the given context."""
        ...

    def list_templates(self) -> list[str]:
        """List all available template names."""
        ...
