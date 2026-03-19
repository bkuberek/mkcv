"""Resolve a job description from file path, URL, or stdin."""

import asyncio
import logging
import sys
from pathlib import Path

import httpx

from mkcv.core.exceptions.jd_read import JDReadError

logger = logging.getLogger(__name__)

_STDIN_SENTINELS = ("-", "")


def _is_url(source: str) -> bool:
    """Check whether the source looks like an HTTP(S) URL."""
    return source.startswith("http://") or source.startswith("https://")


def _read_file(path: Path) -> str:
    """Read JD content from a local file."""
    if not path.is_file():
        raise JDReadError(f"Job description file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise JDReadError(f"Job description file is empty: {path}")
    return text


async def _fetch_url(url: str) -> str:
    """Fetch JD content from a URL using httpx."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise JDReadError(
            f"Failed to fetch JD from URL (HTTP {exc.response.status_code}): {url}"
        ) from exc
    except httpx.RequestError as exc:
        raise JDReadError(f"Failed to fetch JD from URL: {url} ({exc})") from exc

    text = response.text.strip()
    if not text:
        raise JDReadError(f"JD fetched from URL is empty: {url}")
    return text


def _read_stdin() -> str:
    """Read JD content from stdin."""
    if sys.stdin.isatty():
        raise JDReadError(
            "No job description provided. Use --jd <file|url> "
            "or pipe content via stdin."
        )
    text = sys.stdin.read().strip()
    if not text:
        raise JDReadError("Job description from stdin is empty.")
    return text


def read_jd(source: str) -> str:
    """Resolve a JD source string to its text content.

    Synchronous entry point. For URLs, internally runs the async
    fetch via ``asyncio.run``.

    Args:
        source: One of:
            - A file path (reads the file)
            - An HTTP/HTTPS URL (fetches the content)
            - ``"-"`` or ``""`` (reads from stdin)

    Returns:
        The job description text.

    Raises:
        JDReadError: If the source cannot be read or is empty.
    """
    if source in _STDIN_SENTINELS:
        logger.info("Reading JD from stdin")
        return _read_stdin()

    if _is_url(source):
        logger.info("Fetching JD from URL: %s", source)
        return asyncio.run(_fetch_url(source))

    logger.info("Reading JD from file: %s", source)
    return _read_file(Path(source))
