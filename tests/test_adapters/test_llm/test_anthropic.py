"""Tests for AnthropicAdapter with mocked SDK."""

from unittest.mock import AsyncMock, MagicMock

import anthropic
import pytest

from mkcv.adapters.llm.anthropic import AnthropicAdapter
from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.requirement import Requirement


@pytest.fixture
def anthropic_adapter() -> AnthropicAdapter:
    return AnthropicAdapter(api_key="test-key")


class TestAnthropicComplete:
    """Tests for AnthropicAdapter.complete."""

    async def test_complete_returns_text(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = "Hello from Claude"

        mock_response = MagicMock()
        mock_response.content = [mock_block]

        anthropic_adapter._client.messages.create = AsyncMock(
            return_value=mock_response
        )

        result = await anthropic_adapter.complete(
            [{"role": "user", "content": "hi"}],
            model="claude-sonnet-4-20250514",
        )
        assert result == "Hello from Claude"

    async def test_complete_maps_rate_limit_error(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}

        anthropic_adapter._client.messages.create = AsyncMock(
            side_effect=anthropic.RateLimitError(
                message="rate limited",
                response=mock_response,
                body=None,
            )
        )

        with pytest.raises(RateLimitError):
            await anthropic_adapter.complete(
                [{"role": "user", "content": "hi"}],
                model="claude-sonnet-4-20250514",
            )

    async def test_complete_maps_auth_error(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.headers = {}

        anthropic_adapter._client.messages.create = AsyncMock(
            side_effect=anthropic.AuthenticationError(
                message="invalid api key",
                response=mock_response,
                body=None,
            )
        )

        with pytest.raises(AuthenticationError):
            await anthropic_adapter.complete(
                [{"role": "user", "content": "hi"}],
                model="claude-sonnet-4-20250514",
            )


class TestAnthropicCompleteStructured:
    """Tests for AnthropicAdapter.complete_structured."""

    async def test_complete_structured_with_tool_use(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        tool_input = {
            "company": "TestCo",
            "role_title": "Engineer",
            "seniority_level": "Senior",
            "core_requirements": [
                {
                    "skill": "Python",
                    "importance": "must_have",
                    "context": "Backend development",
                }
            ],
            "technical_stack": ["Python"],
            "soft_skills": ["Communication"],
            "leadership_signals": [],
            "culture_keywords": [],
            "ats_keywords": ["Python"],
            "hidden_requirements": [],
            "role_summary": "A senior engineer role.",
        }

        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.name = "extract_jdanalysis"
        mock_block.input = tool_input

        mock_response = MagicMock()
        mock_response.content = [mock_block]

        anthropic_adapter._client.messages.create = AsyncMock(
            return_value=mock_response
        )

        result = await anthropic_adapter.complete_structured(
            [{"role": "user", "content": "analyze this JD"}],
            model="claude-sonnet-4-20250514",
            response_model=JDAnalysis,
        )

        assert isinstance(result, JDAnalysis)
        assert result.company == "TestCo"
        assert result.role_title == "Engineer"
        assert len(result.core_requirements) == 1
        assert isinstance(result.core_requirements[0], Requirement)

    async def test_complete_structured_maps_errors(
        self, anthropic_adapter: AnthropicAdapter
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}

        anthropic_adapter._client.messages.create = AsyncMock(
            side_effect=anthropic.RateLimitError(
                message="rate limited",
                response=mock_response,
                body=None,
            )
        )

        with pytest.raises(RateLimitError):
            await anthropic_adapter.complete_structured(
                [{"role": "user", "content": "analyze"}],
                model="claude-sonnet-4-20250514",
                response_model=JDAnalysis,
            )
