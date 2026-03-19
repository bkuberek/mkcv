"""Resolve a job description from file path, URL, or stdin."""

import asyncio
import logging
import re
import sys
from pathlib import Path

import httpx
from ruamel.yaml import YAML, YAMLError  # type: ignore[attr-defined]

from mkcv.core.exceptions.jd_read import JDReadError
from mkcv.core.models.jd_document import JDDocument
from mkcv.core.models.jd_frontmatter import JDFrontmatter

logger = logging.getLogger(__name__)

_STDIN_SENTINELS = ("-", "")

_FRONTMATTER_PATTERN = re.compile(
    r"\A\s*---\s*\n(.*?)\n---\s*\n(.*)",
    re.DOTALL,
)


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


def parse_jd_document(
    text: str,
    *,
    source_path: Path | None = None,
) -> JDDocument:
    """Parse a JD text that may contain YAML frontmatter.

    If the text starts with ``---``, attempts to parse YAML frontmatter.
    On parse failure, treats the entire text as the body (no metadata).
    Plain text without frontmatter returns ``metadata=None``.

    Args:
        text: Raw JD text content.
        source_path: Optional path to the source file.

    Returns:
        JDDocument with parsed metadata (if any) and body text.

    Raises:
        JDReadError: If the body is empty after frontmatter extraction.
    """
    match = _FRONTMATTER_PATTERN.match(text)
    if match is None:
        return JDDocument(body=text.strip(), source_path=source_path)

    yaml_str, body_str = match.group(1), match.group(2)

    try:
        _yaml = YAML(typ="safe")
        raw = _yaml.load(yaml_str)
    except YAMLError:
        logger.warning(
            "Malformed YAML frontmatter in JD; treating as plain text",
            exc_info=True,
        )
        return JDDocument(body=text.strip(), source_path=source_path)

    if not isinstance(raw, dict):
        return JDDocument(body=text.strip(), source_path=source_path)

    try:
        metadata = JDFrontmatter.model_validate(raw)
    except Exception:
        logger.warning(
            "Invalid JD frontmatter fields; ignoring metadata",
            exc_info=True,
        )
        return JDDocument(body=body_str.strip(), source_path=source_path)

    if not body_str.strip():
        raise JDReadError("JD body is empty after frontmatter")

    return JDDocument(
        metadata=metadata,
        body=body_str.strip(),
        source_path=source_path,
    )


def read_jd(source: str) -> JDDocument:
    """Resolve a JD source string to a JDDocument.

    Synchronous entry point. For URLs, internally runs the async
    fetch via ``asyncio.run``.

    Args:
        source: One of:
            - A file path (reads the file)
            - An HTTP/HTTPS URL (fetches the content)
            - ``"-"`` or ``""`` (reads from stdin)

    Returns:
        JDDocument with optional frontmatter metadata and body text.

    Raises:
        JDReadError: If the source cannot be read or is empty.
    """
    if source in _STDIN_SENTINELS:
        logger.info("Reading JD from stdin")
        text = _read_stdin()
        return parse_jd_document(text)

    if _is_url(source):
        logger.info("Fetching JD from URL: %s", source)
        text = asyncio.run(_fetch_url(source))
        return parse_jd_document(text)

    logger.info("Reading JD from file: %s", source)
    path = Path(source)
    text = _read_file(path)
    return parse_jd_document(text, source_path=path)
