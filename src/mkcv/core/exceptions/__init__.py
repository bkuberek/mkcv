"""mkcv exception hierarchy.

All exceptions inherit from MkcvError. Import from this package:

    from mkcv.core.exceptions import MkcvError, ProviderError, ...
"""

from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.base import MkcvError
from mkcv.core.exceptions.context_length import ContextLengthError
from mkcv.core.exceptions.jd_read import JDReadError
from mkcv.core.exceptions.pipeline_stage import PipelineStageError
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.exceptions.render import RenderError
from mkcv.core.exceptions.template import TemplateError
from mkcv.core.exceptions.validation import ValidationError
from mkcv.core.exceptions.workspace import (
    WorkspaceError,
    WorkspaceExistsError,
    WorkspaceNotFoundError,
)

__all__ = [
    "AuthenticationError",
    "ContextLengthError",
    "JDReadError",
    "MkcvError",
    "PipelineStageError",
    "ProviderError",
    "RateLimitError",
    "RenderError",
    "TemplateError",
    "ValidationError",
    "WorkspaceError",
    "WorkspaceExistsError",
    "WorkspaceNotFoundError",
]
