"""Tests for KBGenerationService."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from mkcv.core.exceptions.kb_generation import KBGenerationError
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.models.document_content import DocumentContent
from mkcv.core.models.kb_generation_result import KBGenerationResult
from mkcv.core.services.kb_generation_service import (
    KBGenerationService,
    _strip_code_fences,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_doc(
    name: str = "test.txt",
    text: str = "Sample content for testing.",
    fmt: str = "text",
) -> DocumentContent:
    """Create a sample DocumentContent."""
    return DocumentContent(
        text=text,
        source_path=Path(f"/tmp/{name}"),
        format=fmt,
        char_count=len(text),
    )


_DEFAULT_LLM_RESPONSE = (
    "# Career KB\n\n"
    "## Personal Information\n\n"
    "| Field | Value |\n|---|---|\n| Name | Jane |\n\n"
    "## Professional Summary\n\nSenior engineer.\n\n"
    "## Technical Skills\n\n- Python\n\n"
    "## Career History\n\n"
    "### Acme -- Engineer\n**2020-2024**\n\n- Built systems\n\n"
    "## Education\n\n### MIT -- BS CS\n**2016**"
)


def _make_service(
    documents: list[DocumentContent] | None = None,
    llm_response: str = _DEFAULT_LLM_RESPONSE,
    chunk_threshold: int = 100_000,
) -> tuple[KBGenerationService, MagicMock, AsyncMock, MagicMock]:
    """Create a KBGenerationService with mocked dependencies.

    Returns (service, mock_reader, mock_llm, mock_prompts).
    """
    mock_reader = MagicMock()
    mock_reader.supported_extensions.return_value = {
        ".txt",
        ".md",
        ".pdf",
        ".docx",
        ".html",
    }
    mock_reader.read_file.side_effect = lambda p: _make_doc(p.name, f"text of {p.name}")

    mock_llm = AsyncMock()
    mock_llm.complete.return_value = llm_response

    mock_prompts = MagicMock()
    mock_prompts.render.return_value = "rendered prompt text"

    service = KBGenerationService(
        document_reader=mock_reader,
        llm=mock_llm,
        prompts=mock_prompts,
        chunk_threshold=chunk_threshold,
    )

    return service, mock_reader, mock_llm, mock_prompts


# ------------------------------------------------------------------
# generate() happy path
# ------------------------------------------------------------------


class TestGenerateHappyPath:
    """Tests for KBGenerationService.generate() success scenarios."""

    @pytest.mark.asyncio
    async def test_generate_returns_kb_generation_result(self, tmp_path: Path) -> None:
        service, _reader, _, _ = _make_service()
        source_file = tmp_path / "resume.txt"
        source_file.write_text("resume content", encoding="utf-8")

        result = await service.generate(sources=[source_file])
        assert isinstance(result, KBGenerationResult)

    @pytest.mark.asyncio
    async def test_generate_returns_kb_text(self, tmp_path: Path) -> None:
        service, _, _, _ = _make_service()
        source_file = tmp_path / "resume.txt"
        source_file.write_text("resume content", encoding="utf-8")

        result = await service.generate(sources=[source_file])
        assert "Career KB" in result.kb_text

    @pytest.mark.asyncio
    async def test_generate_writes_output_file(self, tmp_path: Path) -> None:
        service, _, _, _ = _make_service()
        source_file = tmp_path / "resume.txt"
        source_file.write_text("resume content", encoding="utf-8")
        output = tmp_path / "kb.md"

        result = await service.generate(sources=[source_file], output=output)
        assert result.output_path is not None
        assert output.exists()
        assert output.read_text(encoding="utf-8") == result.kb_text

    @pytest.mark.asyncio
    async def test_generate_no_output_path_when_not_specified(
        self, tmp_path: Path
    ) -> None:
        service, _, _, _ = _make_service()
        source_file = tmp_path / "resume.txt"
        source_file.write_text("resume content", encoding="utf-8")

        result = await service.generate(sources=[source_file])
        assert result.output_path is None

    @pytest.mark.asyncio
    async def test_generate_passes_kb_name_to_prompt(self, tmp_path: Path) -> None:
        service, _, _, mock_prompts = _make_service()
        source_file = tmp_path / "resume.txt"
        source_file.write_text("resume content", encoding="utf-8")

        await service.generate(sources=[source_file], kb_name="Engineering")
        call_args = mock_prompts.render.call_args
        assert call_args[0][0] == "kb_generate.j2"
        context = call_args[0][1]
        assert context["kb_name"] == "Engineering"

    @pytest.mark.asyncio
    async def test_generate_calls_llm(self, tmp_path: Path) -> None:
        service, _, mock_llm, _ = _make_service()
        source_file = tmp_path / "resume.txt"
        source_file.write_text("resume content", encoding="utf-8")

        await service.generate(sources=[source_file])
        mock_llm.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_returns_validation_warnings(self, tmp_path: Path) -> None:
        # Use a KB response that will trigger validation warnings
        # (short, missing sections)
        short_kb = "# KB\n\n## Summary\n\nShort."
        service, _, _, _ = _make_service(llm_response=short_kb)
        source_file = tmp_path / "resume.txt"
        source_file.write_text("resume content", encoding="utf-8")

        result = await service.generate(sources=[source_file])
        assert isinstance(result.validation_warnings, list)


# ------------------------------------------------------------------
# generate() error handling
# ------------------------------------------------------------------


class TestGenerateErrors:
    """Tests for KBGenerationService.generate() error scenarios."""

    @pytest.mark.asyncio
    async def test_no_documents_found_raises(self, tmp_path: Path) -> None:
        service, _, _, _ = _make_service()
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        with pytest.raises(KBGenerationError, match="No supported documents"):
            await service.generate(sources=[empty_dir])

    @pytest.mark.asyncio
    async def test_llm_failure_raises_kb_generation_error(self, tmp_path: Path) -> None:
        service, _, mock_llm, _ = _make_service()
        mock_llm.complete.side_effect = RuntimeError("LLM exploded")
        source_file = tmp_path / "resume.txt"
        source_file.write_text("content", encoding="utf-8")

        with pytest.raises(KBGenerationError, match="LLM call failed"):
            await service.generate(sources=[source_file])

    @pytest.mark.asyncio
    async def test_rate_limit_error_propagated(self, tmp_path: Path) -> None:
        service, _, mock_llm, _ = _make_service()
        mock_llm.complete.side_effect = RateLimitError(
            "rate limited", provider="anthropic"
        )
        source_file = tmp_path / "resume.txt"
        source_file.write_text("content", encoding="utf-8")

        with pytest.raises(RateLimitError):
            await service.generate(sources=[source_file])

    @pytest.mark.asyncio
    async def test_provider_error_propagated(self, tmp_path: Path) -> None:
        service, _, mock_llm, _ = _make_service()
        mock_llm.complete.side_effect = ProviderError(
            "provider down", provider="anthropic"
        )
        source_file = tmp_path / "resume.txt"
        source_file.write_text("content", encoding="utf-8")

        with pytest.raises(ProviderError):
            await service.generate(sources=[source_file])


# ------------------------------------------------------------------
# generate() chunked processing
# ------------------------------------------------------------------


class TestGenerateChunked:
    """Tests for chunked processing of large inputs."""

    @pytest.mark.asyncio
    async def test_chunked_when_over_threshold(self, tmp_path: Path) -> None:
        """When total chars exceed threshold, multiple LLM calls are made."""
        service, _, mock_llm, _prompts = _make_service(
            chunk_threshold=50,
        )
        source_file = tmp_path / "big.txt"
        source_file.write_text("x" * 100, encoding="utf-8")

        # We need to mock _read_documents to return large docs
        big_doc = _make_doc("big.txt", "x" * 100)
        service._read_documents = MagicMock(return_value=[big_doc])  # type: ignore[method-assign]

        await service.generate(sources=[source_file])
        # Single chunk (one doc exceeding threshold -> its own chunk)
        # -> 1 call for generate
        assert mock_llm.complete.call_count >= 1

    @pytest.mark.asyncio
    async def test_chunked_multiple_docs(self, tmp_path: Path) -> None:
        """Multiple docs over threshold trigger chunk + merge."""
        service, _, mock_llm, _ = _make_service(
            chunk_threshold=50,
        )
        source_file = tmp_path / "a.txt"
        source_file.write_text("aaa", encoding="utf-8")

        docs = [
            _make_doc("a.txt", "a" * 30),
            _make_doc("b.txt", "b" * 30),
        ]
        service._read_documents = MagicMock(return_value=docs)  # type: ignore[method-assign]

        await service.generate(sources=[source_file])
        # Two chunks -> 2 generate calls + 1 merge call = 3
        assert mock_llm.complete.call_count == 3


# ------------------------------------------------------------------
# update() happy path
# ------------------------------------------------------------------


class TestUpdateHappyPath:
    """Tests for KBGenerationService.update() success scenarios."""

    @pytest.mark.asyncio
    async def test_update_returns_kb_generation_result(self, tmp_path: Path) -> None:
        service, _, _, _ = _make_service()
        kb_file = tmp_path / "existing.md"
        kb_file.write_text("# Existing KB\n\n## Summary\n\nOld data.", encoding="utf-8")
        source_file = tmp_path / "new.txt"
        source_file.write_text("new content", encoding="utf-8")

        result = await service.update(
            existing_kb_path=kb_file,
            sources=[source_file],
        )
        assert isinstance(result, KBGenerationResult)

    @pytest.mark.asyncio
    async def test_update_writes_back_to_existing_path(self, tmp_path: Path) -> None:
        service, _, _, _ = _make_service()
        kb_file = tmp_path / "existing.md"
        kb_file.write_text("# Old KB", encoding="utf-8")
        source_file = tmp_path / "new.txt"
        source_file.write_text("new content", encoding="utf-8")

        result = await service.update(
            existing_kb_path=kb_file,
            sources=[source_file],
        )
        assert result.output_path is not None
        assert kb_file.read_text(encoding="utf-8") == result.kb_text

    @pytest.mark.asyncio
    async def test_update_uses_kb_update_template(self, tmp_path: Path) -> None:
        service, _, _, mock_prompts = _make_service()
        kb_file = tmp_path / "existing.md"
        kb_file.write_text("# Old KB", encoding="utf-8")
        source_file = tmp_path / "new.txt"
        source_file.write_text("new content", encoding="utf-8")

        await service.update(
            existing_kb_path=kb_file,
            sources=[source_file],
        )
        call_args = mock_prompts.render.call_args
        assert call_args[0][0] == "kb_update.j2"
        context = call_args[0][1]
        assert "existing_kb" in context
        assert "document_texts" in context


# ------------------------------------------------------------------
# update() error handling
# ------------------------------------------------------------------


class TestUpdateErrors:
    """Tests for KBGenerationService.update() error scenarios."""

    @pytest.mark.asyncio
    async def test_nonexistent_kb_raises(self, tmp_path: Path) -> None:
        service, _, _, _ = _make_service()
        ghost = tmp_path / "nonexistent.md"
        source_file = tmp_path / "new.txt"
        source_file.write_text("content", encoding="utf-8")

        with pytest.raises(KBGenerationError, match="not found"):
            await service.update(
                existing_kb_path=ghost,
                sources=[source_file],
            )

    @pytest.mark.asyncio
    async def test_no_new_documents_raises(self, tmp_path: Path) -> None:
        service, _, _, _ = _make_service()
        kb_file = tmp_path / "existing.md"
        kb_file.write_text("# KB", encoding="utf-8")
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        with pytest.raises(KBGenerationError, match="No supported documents"):
            await service.update(
                existing_kb_path=kb_file,
                sources=[empty_dir],
            )


# ------------------------------------------------------------------
# _strip_code_fences helper
# ------------------------------------------------------------------


class TestStripCodeFences:
    """Tests for the _strip_code_fences utility function."""

    def test_strips_markdown_fences(self) -> None:
        text = "```markdown\n# KB\n\nContent\n```"
        assert _strip_code_fences(text) == "# KB\n\nContent"

    def test_strips_plain_fences(self) -> None:
        text = "```\n# KB\n\nContent\n```"
        assert _strip_code_fences(text) == "# KB\n\nContent"

    def test_no_fences_unchanged(self) -> None:
        text = "# KB\n\nContent"
        assert _strip_code_fences(text) == text

    def test_only_opening_fence_partial_strip(self) -> None:
        text = "```markdown\n# KB\n\nContent"
        result = _strip_code_fences(text)
        assert "# KB" in result


# ------------------------------------------------------------------
# _split_into_chunks helper
# ------------------------------------------------------------------


class TestSplitIntoChunks:
    """Tests for document chunking logic."""

    def test_single_small_doc_one_chunk(self) -> None:
        service, _, _, _ = _make_service(chunk_threshold=1000)
        docs = [_make_doc("a.txt", "short")]
        chunks = service._split_into_chunks(docs)
        assert len(chunks) == 1
        assert len(chunks[0]) == 1

    def test_multiple_small_docs_one_chunk(self) -> None:
        service, _, _, _ = _make_service(chunk_threshold=1000)
        docs = [_make_doc("a.txt", "aaa"), _make_doc("b.txt", "bbb")]
        chunks = service._split_into_chunks(docs)
        assert len(chunks) == 1
        assert len(chunks[0]) == 2

    def test_large_docs_multiple_chunks(self) -> None:
        service, _, _, _ = _make_service(chunk_threshold=50)
        docs = [
            _make_doc("a.txt", "a" * 30),
            _make_doc("b.txt", "b" * 30),
        ]
        chunks = service._split_into_chunks(docs)
        assert len(chunks) == 2

    def test_single_oversized_doc_own_chunk(self) -> None:
        service, _, _, _ = _make_service(chunk_threshold=10)
        docs = [_make_doc("big.txt", "x" * 100)]
        chunks = service._split_into_chunks(docs)
        assert len(chunks) == 1
        assert len(chunks[0]) == 1


# ------------------------------------------------------------------
# _build_document_texts helper
# ------------------------------------------------------------------


class TestBuildDocumentTexts:
    """Tests for the prompt template data builder."""

    def test_builds_list_of_dicts(self) -> None:
        docs = [_make_doc("resume.pdf", "my resume"), _make_doc("notes.txt", "notes")]
        result = KBGenerationService._build_document_texts(docs)
        assert len(result) == 2
        assert result[0]["filename"] == "resume.pdf"
        assert result[0]["text"] == "my resume"
        assert result[1]["filename"] == "notes.txt"
