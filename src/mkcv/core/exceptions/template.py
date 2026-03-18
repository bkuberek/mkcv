"""Template error for Jinja2 prompt template issues."""

from mkcv.core.exceptions.base import MkcvError


class TemplateError(MkcvError):
    """Jinja2 template loading or rendering failed."""

    def __init__(self, message: str, *, template_name: str = "") -> None:
        self.template_name = template_name
        super().__init__(message, exit_code=6)
