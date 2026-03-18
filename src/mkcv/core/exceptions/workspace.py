"""Workspace-related errors."""

from mkcv.core.exceptions.base import MkcvError


class WorkspaceError(MkcvError):
    """Error related to workspace operations."""

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=7)


class WorkspaceNotFoundError(WorkspaceError):
    """No workspace found when one is required."""


class WorkspaceExistsError(WorkspaceError):
    """Workspace already exists at the target path."""
