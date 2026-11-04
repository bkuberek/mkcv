"""Where a Vertex AI request goes: the Google Cloud project and location."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class VertexTarget(BaseModel):
    """Resolved Vertex AI destination for the Google adapter."""

    model_config = ConfigDict(frozen=True)

    project: str
    location: str
    credentials: Any = None  # google.auth credentials; None lets the SDK find ADC
