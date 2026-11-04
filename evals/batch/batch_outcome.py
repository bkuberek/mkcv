"""What a batch returned for one request."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BatchOutcome:
    """The provider's response body for one request, or why it has none."""

    custom_id: str
    response: dict[str, Any] | None = None
    error: str | None = None
