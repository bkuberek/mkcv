"""Cloud Storage through its JSON API, with Application Default Credentials."""

import asyncio
import json
from typing import Any
from urllib.parse import quote

from evals.batch.cloud_storage import split_uri

_API = "https://storage.googleapis.com"
_SCOPE = "https://www.googleapis.com/auth/devstorage.read_write"


class GoogleCloudStorage:
    """The Cloud Storage JSON API, authenticated with Application Default Credentials.

    It only reads and writes objects in a bucket that already exists; it
    never creates buckets. Calls run in a thread, as ``google-auth`` sessions
    are synchronous.

    Implements: CloudStorage
    """

    def __init__(self, session: Any | None = None) -> None:
        self._session = session

    async def upload(self, uri: str, text: str) -> None:
        """Write the object."""
        bucket, name = split_uri(uri)
        url = f"{_API}/upload/storage/v1/b/{bucket}/o"
        await asyncio.to_thread(
            self._call,
            "POST",
            url,
            params={"uploadType": "media", "name": name},
            data=text.encode("utf-8"),
            headers={"Content-Type": "application/jsonl"},
        )

    async def read_jsonl(self, prefix_uri: str) -> list[dict[str, Any]]:
        """Read every ``.jsonl`` object under the prefix."""
        bucket, prefix = split_uri(prefix_uri)
        listing = await asyncio.to_thread(
            self._call,
            "GET",
            f"{_API}/storage/v1/b/{bucket}/o",
            params={"prefix": prefix},
        )
        names = [
            item["name"]
            for item in json.loads(listing).get("items", [])
            if str(item.get("name", "")).endswith(".jsonl")
        ]
        lines: list[dict[str, Any]] = []
        for name in sorted(names):
            body = await asyncio.to_thread(
                self._call,
                "GET",
                f"{_API}/storage/v1/b/{bucket}/o/{quote(name, safe='')}",
                params={"alt": "media"},
            )
            lines.extend(json.loads(line) for line in body.splitlines() if line.strip())
        return lines

    def _call(self, method: str, url: str, **options: Any) -> str:
        response = self._authorized().request(method, url, timeout=120, **options)
        response.raise_for_status()
        return str(response.text)

    def _authorized(self) -> Any:
        if self._session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession

            credentials, _ = google.auth.default(scopes=[_SCOPE])
            self._session = AuthorizedSession(credentials)  # type: ignore[no-untyped-call]
        return self._session
