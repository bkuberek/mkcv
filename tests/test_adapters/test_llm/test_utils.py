"""Tests for shared LLM adapter utilities."""

import pytest
from pydantic import BaseModel

from mkcv.adapters.llm._utils import (
    build_schema_prompt,
    extract_json_from_text,
    split_system_message,
    validate_structured_response,
)
from mkcv.core.exceptions.validation import ValidationError


class _SampleModel(BaseModel):
    name: str
    score: int


class TestExtractJsonFromText:
    """Tests for extract_json_from_text."""

    def test_extract_json_direct_parse(self) -> None:
        raw = '{"name": "Alice", "score": 42}'
        result = extract_json_from_text(raw)
        assert result == {"name": "Alice", "score": 42}

    def test_extract_json_from_json_fence(self) -> None:
        text = 'Here is the result:\n```json\n{"name": "Bob", "score": 7}\n```\n'
        result = extract_json_from_text(text)
        assert result == {"name": "Bob", "score": 7}

    def test_extract_json_from_plain_fence(self) -> None:
        text = 'Output:\n```\n{"key": "value"}\n```\n'
        result = extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_extract_json_from_embedded_braces(self) -> None:
        text = 'Some preamble text. {"a": 1, "b": 2} and trailing text.'
        result = extract_json_from_text(text)
        assert result == {"a": 1, "b": 2}

    def test_extract_json_raises_on_invalid(self) -> None:
        with pytest.raises(ValueError, match="Could not extract valid JSON"):
            extract_json_from_text("No JSON here at all")


class TestValidateStructuredResponse:
    """Tests for validate_structured_response."""

    def test_validate_structured_response_valid(self) -> None:
        data = {"name": "Alice", "score": 42}
        result = validate_structured_response(data, _SampleModel)
        assert isinstance(result, _SampleModel)
        assert result.name == "Alice"
        assert result.score == 42

    def test_validate_structured_response_invalid(self) -> None:
        data = {"name": "Alice"}  # missing required 'score'
        with pytest.raises(ValidationError, match="failed validation"):
            validate_structured_response(data, _SampleModel)


class TestBuildSchemaPrompt:
    """Tests for build_schema_prompt."""

    def test_build_schema_prompt_includes_schema(self) -> None:
        prompt = build_schema_prompt(_SampleModel)
        assert "_SampleModel" not in prompt or "SampleModel" in prompt
        assert '"name"' in prompt
        assert '"score"' in prompt
        assert "JSON" in prompt


class TestSplitSystemMessage:
    """Tests for split_system_message."""

    def test_split_system_message_with_system(self) -> None:
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        system, remaining = split_system_message(messages)
        assert system == "You are helpful."
        assert remaining == [{"role": "user", "content": "Hello"}]

    def test_split_system_message_without_system(self) -> None:
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        system, remaining = split_system_message(messages)
        assert system is None
        assert len(remaining) == 2
