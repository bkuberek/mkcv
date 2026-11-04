"""Kinds of LLM provider a configured provider name can resolve to."""

from enum import StrEnum


class ProviderKind(StrEnum):
    """The wire protocol and SDK behind a named provider."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    OPENAI_COMPATIBLE = "openai-compatible"
    STUB = "stub"
