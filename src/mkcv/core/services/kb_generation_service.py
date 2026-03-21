"""Knowledge base generation service."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar

from mkcv.core.exceptions.authentication import AuthenticationError
from mkcv.core.exceptions.context_length import ContextLengthError
from mkcv.core.exceptions.kb_generation import KBGenerationError
from mkcv.core.exceptions.provider import ProviderError
from mkcv.core.exceptions.rate_limit import RateLimitError
from mkcv.core.exceptions.validation import ValidationError
from mkcv.core.models.document_content import DocumentContent
from mkcv.core.models.kb_generation_result import KBGenerationResult
from mkcv.core.ports.document_reader import DocumentReaderPort
from mkcv.core.ports.llm import LLMPort
from mkcv.core.ports.prompts import PromptLoaderPort
from mkcv.core.services.kb_validator import validate_kb

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 8192
CHUNK_CHAR_THRESHOLD = 100_000

_R = TypeVar("_R")


class KBGenerationService:
    """Generates and updates structured Markdown knowledge bases from source documents.

    Takes source documents (PDF, Markdown, DOCX, HTML, TXT), reads them via
    a DocumentReaderPort, synthesises content through an LLM, validates the
    output, and writes the result to disk.

    For large inputs exceeding the chunk threshold, documents are processed
    in chunks and then merged into a single KB.
    """

    def __init__(
        self,
        document_reader: DocumentReaderPort,
        llm: LLMPort,
        prompts: PromptLoaderPort,
        *,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.3,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        chunk_threshold: int = CHUNK_CHAR_THRESHOLD,
    ) -> None:
        self._reader = document_reader
        self._llm = llm
        self._prompts = prompts
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._chunk_threshold = chunk_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(
        self,
        sources: list[Path],
        output: Path | None = None,
        kb_name: str = "Career",
        glob: str | None = None,
    ) -> KBGenerationResult:
        """Generate a knowledge base from source documents.

        Reads all supported files from *sources* (files or directories),
        renders the kb_generate prompt, calls the LLM, validates the
        output, and optionally writes to *output*.

        When total character count exceeds the chunk threshold, documents
        are split into chunks, partial KBs are generated, and then merged
        into a final result.

        Args:
            sources: File and/or directory paths containing source documents.
            output: Path to write the resulting KB file. When ``None``, the
                KB text is returned but not written to disk.
            kb_name: Name used in the KB title heading (default "Career").
            glob: Glob pattern for directory scanning. ``None`` uses the
                adapter default (``**/*``).

        Returns:
            KBGenerationResult with the generated text, source metadata,
            output path, and any validation warnings.

        Raises:
            KBGenerationError: If no documents are found or the LLM call fails.
            DocumentReadError: If individual files cannot be read.
        """
        documents = self._read_documents(sources, glob=glob)

        if not documents:
            supported = ", ".join(sorted(self._reader.supported_extensions()))
            raise KBGenerationError(
                "No supported documents found in the "
                f"provided sources. Supported formats: {supported}"
            )

        logger.info(
            "Generating KB '%s' from %d document(s) (%d total chars)",
            kb_name,
            len(documents),
            sum(d.char_count for d in documents),
        )

        total_chars = sum(d.char_count for d in documents)

        if total_chars > self._chunk_threshold:
            kb_text = await self._generate_chunked(documents, kb_name=kb_name)
        else:
            kb_text = await self._generate_single(documents, kb_name=kb_name)

        # Strip markdown code fences if the LLM wraps output
        kb_text = _strip_code_fences(kb_text)

        # Validate the generated KB
        validation = validate_kb(kb_text)
        warnings = validation.warnings

        # Write output if path provided
        output_path: Path | None = None
        if output is not None:
            output_path = self._write_output(kb_text, output)

        logger.info(
            "KB generation complete: %d chars, %d warnings",
            len(kb_text),
            len(warnings),
        )

        return KBGenerationResult(
            kb_text=kb_text,
            source_documents=documents,
            output_path=output_path,
            validation_warnings=warnings,
        )

    async def update(
        self,
        existing_kb_path: Path,
        sources: list[Path],
        glob: str | None = None,
    ) -> KBGenerationResult:
        """Update an existing knowledge base with new source documents.

        Reads the existing KB and new documents, renders the kb_update
        prompt, calls the LLM, validates the result, and writes the
        updated KB back to the existing path.

        Args:
            existing_kb_path: Path to the existing KB Markdown file.
            sources: File and/or directory paths containing new documents.
            glob: Glob pattern for directory scanning. ``None`` uses the
                adapter default (``**/*``).

        Returns:
            KBGenerationResult with the updated text, source metadata,
            output path, and any validation warnings.

        Raises:
            KBGenerationError: If the existing KB cannot be read, no new
                documents are found, or the LLM call fails.
            DocumentReadError: If individual files cannot be read.
        """
        if not existing_kb_path.is_file():
            raise KBGenerationError(
                f"Existing knowledge base not found: {existing_kb_path}"
            )

        try:
            existing_kb = existing_kb_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise KBGenerationError(
                f"Cannot read existing knowledge base '{existing_kb_path}': {exc}"
            ) from exc

        documents = self._read_documents(sources, glob=glob)

        if not documents:
            supported = ", ".join(sorted(self._reader.supported_extensions()))
            raise KBGenerationError(
                "No supported documents found in the "
                f"provided sources. Supported formats: {supported}"
            )

        logger.info(
            "Updating KB '%s' with %d new document(s) (%d total chars)",
            existing_kb_path.name,
            len(documents),
            sum(d.char_count for d in documents),
        )

        document_texts = self._build_document_texts(documents)

        prompt = self._prompts.render(
            "kb_update.j2",
            {
                "existing_kb": existing_kb,
                "document_texts": document_texts,
            },
        )

        kb_text = await self._call_llm(prompt)

        # Strip markdown code fences if the LLM wraps output
        kb_text = _strip_code_fences(kb_text)

        # Validate the updated KB
        validation = validate_kb(kb_text)
        warnings = validation.warnings

        # Write back to the existing path
        output_path = self._write_output(kb_text, existing_kb_path)

        logger.info(
            "KB update complete: %d chars, %d warnings",
            len(kb_text),
            len(warnings),
        )

        return KBGenerationResult(
            kb_text=kb_text,
            source_documents=documents,
            output_path=output_path,
            validation_warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Document reading
    # ------------------------------------------------------------------

    def _read_documents(
        self,
        sources: list[Path],
        *,
        glob: str | None,
    ) -> list[DocumentContent]:
        """Read documents from source paths using the document reader.

        Args:
            sources: File and/or directory paths.
            glob: Optional glob pattern for directory scanning.

        Returns:
            List of document contents, sorted by source path.

        Raises:
            DocumentReadError: If a file cannot be read.
        """
        # The adapter's read_sources handles both files and directories
        # and supports the glob parameter for directory scanning.
        # We need to call the port's read_file for each file individually
        # since the port only defines read_file, not read_sources.
        supported = self._reader.supported_extensions()
        effective_glob = glob or "**/*"

        discovered: set[Path] = set()
        for p in sources:
            resolved = p.resolve()
            if resolved.is_file():
                if resolved.suffix.lower() in supported:
                    discovered.add(resolved)
                else:
                    logger.debug("Skipping unsupported file: %s", resolved)
            elif resolved.is_dir():
                for child in resolved.glob(effective_glob):
                    if child.is_file() and child.suffix.lower() in supported:
                        discovered.add(child)
            else:
                logger.warning("Path does not exist, skipping: %s", resolved)

        results: list[DocumentContent] = []
        for file_path in sorted(discovered):
            logger.info("Reading %s", file_path)
            results.append(self._reader.read_file(file_path))

        return results

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------

    async def _generate_single(
        self,
        documents: list[DocumentContent],
        *,
        kb_name: str,
    ) -> str:
        """Generate a KB from all documents in a single LLM call.

        Args:
            documents: Source documents to include.
            kb_name: Name for the KB title heading.

        Returns:
            Generated KB Markdown text.
        """
        document_texts = self._build_document_texts(documents)

        prompt = self._prompts.render(
            "kb_generate.j2",
            {
                "document_texts": document_texts,
                "kb_name": kb_name,
            },
        )

        return await self._call_llm(prompt)

    async def _generate_chunked(
        self,
        documents: list[DocumentContent],
        *,
        kb_name: str,
    ) -> str:
        """Generate a KB by processing documents in chunks, then merging.

        Splits documents into groups that each fit under the chunk
        threshold, generates a partial KB for each chunk, then merges
        all partial KBs into a final result.

        Args:
            documents: Source documents to include.
            kb_name: Name for the KB title heading.

        Returns:
            Merged KB Markdown text.
        """
        chunks = self._split_into_chunks(documents)

        logger.info(
            "Large input (%d chars) — splitting into %d chunks",
            sum(d.char_count for d in documents),
            len(chunks),
        )

        # Generate partial KBs for each chunk
        partial_kbs: list[str] = []
        for i, chunk in enumerate(chunks, start=1):
            logger.info(
                "Processing chunk %d/%d (%d documents, %d chars)",
                i,
                len(chunks),
                len(chunk),
                sum(d.char_count for d in chunk),
            )
            partial = await self._generate_single(chunk, kb_name=kb_name)
            partial_kbs.append(partial)

        # If only one chunk, no merge needed
        if len(partial_kbs) == 1:
            return partial_kbs[0]

        # Merge all partial KBs by treating each as a "document"
        return await self._merge_partial_kbs(partial_kbs, kb_name=kb_name)

    async def _merge_partial_kbs(
        self,
        partial_kbs: list[str],
        *,
        kb_name: str,
    ) -> str:
        """Merge multiple partial KBs into a single unified KB.

        Uses the update prompt iteratively: starts with the first partial
        KB and merges each subsequent one into it.

        Args:
            partial_kbs: List of partial KB Markdown texts.
            kb_name: Name for the KB title heading.

        Returns:
            Merged KB Markdown text.
        """
        merged = partial_kbs[0]

        for i, partial in enumerate(partial_kbs[1:], start=2):
            logger.info("Merging partial KB %d/%d", i, len(partial_kbs))

            document_texts = [
                {"filename": f"partial_kb_{i}.md", "text": partial},
            ]

            prompt = self._prompts.render(
                "kb_update.j2",
                {
                    "existing_kb": merged,
                    "document_texts": document_texts,
                },
            )

            merged = await self._call_llm(prompt)

        return merged

    async def _call_llm(self, prompt: str) -> str:
        """Send a prompt to the LLM and return the text response.

        Wraps the LLM call with retry logic for transient failures.

        Args:
            prompt: The rendered prompt text.

        Returns:
            LLM response text.

        Raises:
            KBGenerationError: After all retries are exhausted.
        """
        messages: list[dict[str, str]] = [
            {"role": "user", "content": prompt},
        ]

        return await self._call_with_retry(
            lambda: self._do_complete(messages),
            stage_name="kb_generation",
        )

    async def _do_complete(self, messages: list[dict[str, str]]) -> str:
        """Execute a single LLM completion call.

        Args:
            messages: Chat messages to send.

        Returns:
            LLM response text.

        Raises:
            KBGenerationError: On unexpected errors.
        """
        try:
            return await self._llm.complete(
                messages,
                model=self._model,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
        except KBGenerationError:
            raise
        except (ValidationError, ValueError):
            raise
        except (
            RateLimitError,
            AuthenticationError,
            ContextLengthError,
            ProviderError,
        ):
            raise
        except Exception as exc:
            raise KBGenerationError(f"KB generation LLM call failed: {exc}") from exc

    async def _call_with_retry(
        self,
        coro_fn: Callable[[], Awaitable[_R]],
        *,
        stage_name: str,
        max_retries: int = 3,
    ) -> _R:
        """Call an async function with retries on transient failures.

        Retries on ``ValidationError`` and ``ValueError`` (transient LLM
        output quality issues).  Non-retryable provider errors are raised
        immediately.

        Args:
            coro_fn: Zero-argument async callable that produces the result.
            stage_name: Human-readable name for log messages.
            max_retries: Maximum number of attempts (default 3).

        Returns:
            The value produced by *coro_fn*.

        Raises:
            KBGenerationError: After all retries are exhausted.
            RateLimitError: Immediately on rate-limit errors.
            AuthenticationError: Immediately on auth errors.
            ContextLengthError: Immediately on context-length errors.
            ProviderError: Immediately on other provider errors.
        """
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                return await coro_fn()
            except (
                RateLimitError,
                AuthenticationError,
                ContextLengthError,
                ProviderError,
            ):
                raise
            except (ValidationError, ValueError) as exc:
                last_error = exc
                if attempt < max_retries:
                    logger.warning(
                        "%s attempt %d/%d failed: %s. Retrying...",
                        stage_name,
                        attempt,
                        max_retries,
                        exc,
                    )
                    await asyncio.sleep(1.0 * attempt)

        raise KBGenerationError(
            f"{stage_name} failed after {max_retries} attempts: {last_error}"
        ) from last_error

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_document_texts(
        documents: list[DocumentContent],
    ) -> list[dict[str, str]]:
        """Build the document_texts list expected by prompt templates.

        Each entry has ``filename`` and ``text`` keys matching the
        Jinja2 template variables in ``kb_generate.j2`` and ``kb_update.j2``.

        Args:
            documents: Source document contents.

        Returns:
            List of dicts with ``filename`` and ``text`` keys.
        """
        return [
            {
                "filename": doc.source_path.name,
                "text": doc.text,
            }
            for doc in documents
        ]

    def _split_into_chunks(
        self,
        documents: list[DocumentContent],
    ) -> list[list[DocumentContent]]:
        """Split documents into chunks that each fit under the threshold.

        Each chunk tries to stay under ``self._chunk_threshold`` total
        characters. A single document that exceeds the threshold gets
        its own chunk.

        Args:
            documents: Source documents sorted by path.

        Returns:
            List of document groups (chunks).
        """
        chunks: list[list[DocumentContent]] = []
        current_chunk: list[DocumentContent] = []
        current_chars = 0

        for doc in documents:
            if current_chunk and current_chars + doc.char_count > self._chunk_threshold:
                chunks.append(current_chunk)
                current_chunk = []
                current_chars = 0

            current_chunk.append(doc)
            current_chars += doc.char_count

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    @staticmethod
    def _write_output(kb_text: str, output_path: Path) -> Path:
        """Write generated KB text to a file.

        Creates parent directories if they do not exist.

        Args:
            kb_text: The KB Markdown content.
            output_path: Destination file path.

        Returns:
            The resolved output path.

        Raises:
            KBGenerationError: If writing fails.
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(kb_text, encoding="utf-8")
        except OSError as exc:
            raise KBGenerationError(
                f"Failed to write knowledge base to '{output_path}': {exc}"
            ) from exc

        logger.info("Knowledge base written to %s", output_path)
        return output_path.resolve()


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences wrapping content."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # Remove opening fence (```markdown or ```)
        first_newline = stripped.index("\n")
        stripped = stripped[first_newline + 1 :]
    if stripped.endswith("```"):
        stripped = stripped[:-3].rstrip()
    return stripped
