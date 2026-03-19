"""Batch render result models for multi-theme rendering."""

from typing import Literal

from pydantic import BaseModel

from mkcv.core.ports.renderer import RenderedOutput


class ThemeRenderResult(BaseModel):
    """Result of rendering a single theme."""

    theme: str
    status: Literal["success", "error"]
    output: RenderedOutput | None = None
    error_message: str | None = None


class BatchRenderResult(BaseModel):
    """Aggregate result of rendering multiple themes."""

    results: list[ThemeRenderResult]

    @property
    def total(self) -> int:
        """Total number of themes attempted."""
        return len(self.results)

    @property
    def succeeded(self) -> int:
        """Number of themes rendered successfully."""
        return sum(1 for r in self.results if r.status == "success")

    @property
    def failed(self) -> int:
        """Number of themes that failed to render."""
        return sum(1 for r in self.results if r.status == "error")

    @property
    def all_succeeded(self) -> bool:
        """Whether every theme rendered successfully."""
        return self.failed == 0
