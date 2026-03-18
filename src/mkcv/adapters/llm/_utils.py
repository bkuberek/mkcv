"""Shared utilities for LLM provider adapters."""

import json
import logging
import re
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


def extract_json_from_text(text: str) -> dict[str, Any]:
    """Extract JSON from text that may contain markdown code fences.

    Tries in order:
    1. Direct JSON parse of the full text
    2. Extract from ```json ... ``` code fence
    3. Extract from ``` ... ``` code fence
    4. Find first { ... } or [ ... ] block

    Args:
        text: Raw text potentially containing JSON.

    Returns:
        Parsed JSON as a dict.

    Raises:
        ValueError: If no valid JSON can be extracted.
    """
    # Try 1: Direct parse
    text = text.strip()
    try:
        return json.loads(text)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        pass

    # Try 2: Extract from ```json ... ```
    json_fence = re.search(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if json_fence:
        try:
            return json.loads(json_fence.group(1))  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

    # Try 3: Extract from ``` ... ```
    any_fence = re.search(r"```\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if any_fence:
        try:
            return json.loads(any_fence.group(1))  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

    # Try 4: Find first { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

    msg = f"Could not extract valid JSON from text: {text[:200]}..."
    raise ValueError(msg)


def validate_structured_response(
    data: dict[str, Any],
    response_model: type[BaseModel],
) -> BaseModel:
    """Validate a JSON dict against a Pydantic model.

    Args:
        data: Parsed JSON data.
        response_model: The Pydantic model class to validate against.

    Returns:
        A validated instance of response_model.

    Raises:
        ValidationError: If the data doesn't match the model schema.
    """
    from mkcv.core.exceptions.validation import (
        ValidationError as MkcvValidationError,
    )

    try:
        return response_model.model_validate(data)
    except Exception as e:
        raise MkcvValidationError(
            f"LLM response failed validation against {response_model.__name__}: {e}"
        ) from e


def build_schema_prompt(response_model: type[BaseModel]) -> str:
    """Build a prompt instruction describing the expected JSON schema.

    Args:
        response_model: The Pydantic model class.

    Returns:
        A string instructing the LLM to respond with valid JSON.
    """
    schema = response_model.model_json_schema()
    schema_str = json.dumps(schema, indent=2)
    return (
        f"\n\nYou MUST respond with valid JSON matching this schema:\n"
        f"```json\n{schema_str}\n```\n"
        f"Respond ONLY with the JSON object, no other text."
    )


def split_system_message(
    messages: list[dict[str, str]],
) -> tuple[str | None, list[dict[str, str]]]:
    """Split system message from user/assistant messages.

    Anthropic requires system message as a separate parameter.
    This helper extracts it.

    Args:
        messages: List of message dicts with 'role' and 'content' keys.

    Returns:
        Tuple of (system_message_or_None, remaining_messages).
    """
    system = None
    remaining = []
    for msg in messages:
        if msg["role"] == "system":
            system = msg["content"]
        else:
            remaining.append(msg)
    return system, remaining
