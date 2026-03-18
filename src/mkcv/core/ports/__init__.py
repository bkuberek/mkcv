"""Port interfaces for dependency inversion.

Ports are Protocol classes that define the boundaries between
the core domain and external adapters. Core services depend
on these protocols, never on concrete implementations.

    from mkcv.core.ports import LLMPort, RendererPort, ...
"""

from mkcv.core.ports.artifacts import ArtifactStorePort
from mkcv.core.ports.llm import LLMPort
from mkcv.core.ports.prompts import PromptLoaderPort
from mkcv.core.ports.renderer import RenderedOutput, RendererPort

__all__ = [
    "ArtifactStorePort",
    "LLMPort",
    "PromptLoaderPort",
    "RenderedOutput",
    "RendererPort",
]
