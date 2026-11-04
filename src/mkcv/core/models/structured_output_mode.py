"""Ways a provider can be asked to return schema-shaped output."""

from enum import StrEnum


class StructuredOutputMode(StrEnum):
    """How a structured completion constrains the model's reply.

    ``TOOL`` is meaningful only to the Anthropic adapter (a forced tool
    call); every other adapter treats it as ``JSON_SCHEMA``.
    """

    JSON_SCHEMA = "json_schema"
    TOOL = "tool"
    JSON_OBJECT = "json_object"
    PROMPT = "prompt"
