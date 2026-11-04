"""Detect request parameters a provider rejected, from its error message.

Adapters use these helpers to adapt a request once (drop ``temperature`` or
switch the output-limit parameter) instead of failing, because the rules for
new models are not always known in advance.
"""

from typing import Literal

_TEMPERATURE_REJECTION_PHRASES = (
    "unsupported",
    "not supported",
    "does not support",
    "only the default",
    "not allowed",
    "invalid",
)

_STRUCTURED_OUTPUT_MARKERS = (
    "response_format",
    "json_schema",
    "json_object",
    "structured output",
    "response schema",
)


def rejected_parameter(message: str) -> Literal["temperature", "max_tokens"] | None:
    """Return the request parameter an error message says was rejected.

    ``"temperature"`` when the message names it together with a rejection
    phrase; ``"max_tokens"`` when the message tells the caller to use
    ``max_completion_tokens`` instead; otherwise None.
    """
    lowered = message.lower()
    if "temperature" in lowered and any(
        phrase in lowered for phrase in _TEMPERATURE_REJECTION_PHRASES
    ):
        return "temperature"
    if "max_tokens" in lowered and "max_completion_tokens" in lowered:
        return "max_tokens"
    return None


def is_structured_output_rejection(message: str) -> bool:
    """Return True when an error message says the structured-output mode failed.

    A message that rejects ``temperature`` or ``max_tokens`` is a parameter
    rejection, not a structured-output rejection, even if it mentions
    ``response_format``.
    """
    lowered = message.lower()
    names_structured_output = any(
        marker in lowered for marker in _STRUCTURED_OUTPUT_MARKERS
    )
    return names_structured_output and rejected_parameter(message) is None
