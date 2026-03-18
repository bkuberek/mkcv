"""Tests for OpenAIAdapter with mocked SDK."""

import json
from unittest.mock import AsyncMock, MagicMock

import openai
import pytest

from mkcv.adapters.llm.openai import OpenAIAdapter
from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.requirement import Requirement


@pytest.fixture
def openai_adapter() -> OpenAIAdapter:
    return OpenAIAdapter(api_key="test-key")


class TestOpenAIComplete:
    """Tests for OpenAIAdapter.complete."""

    async def test_complete_returns_text(self, openai_adapter: OpenAIAdapter) -> None:
        mock_message = MagicMock()
        mock_message.content = "Hello from GPT"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        openai_adapter._client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        result = await openai_adapter.complete(
            [{"role": "user", "content": "hi"}],
            model="gpt-4o",
        )
        assert result == "Hello from GPT"

    async def test_complete_maps_rate_limit_error(
        self, openai_adapter: OpenAIAdapter
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}

        openai_adapter._client.chat.completions.create = AsyncMock(
            side_effect=openai.RateLimitError(
                message="rate limited",
                response=mock_response,
                body=None,
            )
        )

        with pytest.raises(RateLimitError):
            await openai_adapter.complete(
                [{"role": "user", "content": "hi"}],
                model="gpt-4o",
            )

    async def test_complete_maps_auth_error(
        self, openai_adapter: OpenAIAdapter
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.headers = {}

        openai_adapter._client.chat.completions.create = AsyncMock(
            side_effect=openai.AuthenticationError(
                message="invalid api key",
                response=mock_response,
                body=None,
            )
        )

        with pytest.raises(AuthenticationError):
            await openai_adapter.complete(
                [{"role": "user", "content": "hi"}],
                model="gpt-4o",
            )


class TestOpenAICompleteStructured:
    """Tests for OpenAIAdapter.complete_structured."""

    async def test_complete_structured_returns_model(
        self, openai_adapter: OpenAIAdapter
    ) -> None:
        jd_data = {
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

        mock_message = MagicMock()
        mock_message.content = json.dumps(jd_data)

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        openai_adapter._client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        result = await openai_adapter.complete_structured(
            [{"role": "user", "content": "analyze this JD"}],
            model="gpt-4o",
            response_model=JDAnalysis,
        )

        assert isinstance(result, JDAnalysis)
        assert result.company == "TestCo"
        assert result.role_title == "Engineer"
        assert len(result.core_requirements) == 1
        assert isinstance(result.core_requirements[0], Requirement)

    async def test_complete_structured_maps_errors(
        self, openai_adapter: OpenAIAdapter
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}

        openai_adapter._client.chat.completions.create = AsyncMock(
            side_effect=openai.RateLimitError(
                message="rate limited",
                response=mock_response,
                body=None,
            )
        )

        with pytest.raises(RateLimitError):
            await openai_adapter.complete_structured(
                [{"role": "user", "content": "analyze"}],
                model="gpt-4o",
                response_model=JDAnalysis,
            )
