"""mkcv configuration management.

The settings singleton is created on import and can be used throughout
the application:

    from mkcv.config import settings

    theme = settings.rendering.theme
    verbose = settings.general.verbose
"""

from mkcv.config.configuration import Configuration
from mkcv.config.workspace import find_workspace_root, is_workspace

settings = Configuration()

__all__ = [
    "Configuration",
    "find_workspace_root",
    "is_workspace",
    "settings",
]
