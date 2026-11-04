"""A batch a provider accepted."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SubmittedBatch:
    """A batch's ID, its requests, and where it lives.

    ``extra`` holds provider details needed to collect it later (the Vertex
    AI input and output paths in Cloud Storage, say).
    """

    provider: str
    model: str
    batch_id: str
    custom_ids: tuple[str, ...]
    extra: dict[str, str] = field(default_factory=dict)
