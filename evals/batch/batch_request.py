"""One request of a provider batch."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BatchRequest:
    """A request's ID and the request body the provider takes."""

    custom_id: str
    params: dict[str, Any]
