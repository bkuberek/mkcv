"""Tests for StubLLMAdapter."""

import pytest
from pydantic import BaseModel

from mkcv.adapters.llm.stub import StubLLMAdapter


class _DummyModel(BaseModel):
    value: str


class TestStubComplete:
    """Tests for StubLLMAdapter.complete."""

    async def test_complete_returns_empty_by_default(self) -> None:
        stub = StubLLMAdapter()
        result = await stub.complete(
            [{"role": "user", "content": "hi"}],
            model="test-model",
        )
        assert result == ""

    async def test_complete_returns_default_response(self) -> None:
        stub = StubLLMAdapter(default_response="Hello!")
        result = await stub.complete(
            [{"role": "user", "content": "hi"}],
            model="test-model",
        )
        assert result == "Hello!"


class TestStubCompleteStructured:
    """Tests for StubLLMAdapter.complete_structured."""

    async def test_complete_structured_returns_canned_response(self) -> None:
        canned = _DummyModel(value="canned")
        stub = StubLLMAdapter(responses={_DummyModel: canned})
        result = await stub.complete_structured(
            [{"role": "user", "content": "hi"}],
            model="test-model",
            response_model=_DummyModel,
        )
        assert isinstance(result, _DummyModel)
        assert result.value == "canned"

    async def test_complete_structured_raises_for_unconfigured_model(self) -> None:
        stub = StubLLMAdapter()
        with pytest.raises(NotImplementedError, match="No canned response"):
            await stub.complete_structured(
                [{"role": "user", "content": "hi"}],
                model="test-model",
                response_model=_DummyModel,
            )


class TestStubCallLog:
    """Tests for StubLLMAdapter call logging."""

    async def test_call_log_records_calls(self) -> None:
        stub = StubLLMAdapter()
        await stub.complete(
            [{"role": "user", "content": "hi"}],
            model="test-model",
        )
        assert len(stub.call_log) == 1
        assert stub.call_log[0]["method"] == "complete"
        assert stub.call_log[0]["model"] == "test-model"

    async def test_reset_clears_log(self) -> None:
        stub = StubLLMAdapter()
        await stub.complete(
            [{"role": "user", "content": "hi"}],
            model="test-model",
        )
        assert len(stub.call_log) == 1
        stub.reset()
        assert len(stub.call_log) == 0
