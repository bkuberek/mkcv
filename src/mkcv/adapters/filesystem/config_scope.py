"""Which config file a template is rendered for."""

from enum import StrEnum


class ConfigScope(StrEnum):
    """The two places mkcv reads settings from, besides the built-in defaults."""

    USER = "user"
    WORKSPACE = "workspace"
