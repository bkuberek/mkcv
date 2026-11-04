"""Write and read Vertex AI batch files in Google Cloud Storage."""

from typing import Any, Protocol


class CloudStorage(Protocol):
    """Upload one text object; read every JSON line under a prefix."""

    async def upload(self, uri: str, text: str) -> None:
        """Write ``text`` to ``gs://bucket/object``."""
        ...

    async def read_jsonl(self, prefix_uri: str) -> list[dict[str, Any]]:
        """Return the JSON lines of every ``.jsonl`` object under the prefix."""
        ...


def split_uri(uri: str) -> tuple[str, str]:
    """Split ``gs://bucket/path`` into the bucket and the object path.

    Raises:
        ValueError: If ``uri`` is not a ``gs://`` URI with a bucket.
    """
    if not uri.startswith("gs://"):
        raise ValueError(f"not a gs:// URI: {uri}")
    bucket, _, path = uri.removeprefix("gs://").partition("/")
    if not bucket:
        raise ValueError(f"no bucket in {uri}")
    return bucket, path
