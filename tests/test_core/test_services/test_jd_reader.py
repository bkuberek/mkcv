"""Tests for JD source resolution (file, URL, stdin)."""

import io
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mkcv.core.exceptions.jd_read import JDReadError
from mkcv.core.services.jd_reader import read_jd

# ------------------------------------------------------------------
# Test: File path reads content
# ------------------------------------------------------------------


class TestReadJDFromFile:
    """Tests for reading JD from a local file path."""

    def test_reads_file_content(self, tmp_path: Path) -> None:
        jd_file = tmp_path / "jd.txt"
        jd_file.write_text("Senior Engineer at Acme Corp", encoding="utf-8")

        result = read_jd(str(jd_file))

        assert result == "Senior Engineer at Acme Corp"

    def test_strips_whitespace(self, tmp_path: Path) -> None:
        jd_file = tmp_path / "jd.txt"
        jd_file.write_text("\n  Senior Engineer at Acme Corp  \n", encoding="utf-8")

        result = read_jd(str(jd_file))

        assert result == "Senior Engineer at Acme Corp"

    def test_file_not_found_raises_jd_read_error(self) -> None:
        with pytest.raises(JDReadError, match="not found"):
            read_jd("/nonexistent/path/to/jd.txt")

    def test_empty_file_raises_jd_read_error(self, tmp_path: Path) -> None:
        jd_file = tmp_path / "empty.txt"
        jd_file.write_text("", encoding="utf-8")

        with pytest.raises(JDReadError, match="empty"):
            read_jd(str(jd_file))

    def test_whitespace_only_file_raises_jd_read_error(
        self,
        tmp_path: Path,
    ) -> None:
        jd_file = tmp_path / "blank.txt"
        jd_file.write_text("   \n\n  ", encoding="utf-8")

        with pytest.raises(JDReadError, match="empty"):
            read_jd(str(jd_file))


# ------------------------------------------------------------------
# Test: URL fetches content
# ------------------------------------------------------------------


class TestReadJDFromURL:
    """Tests for fetching JD from a URL."""

    def test_fetches_url_content(self) -> None:
        mock_fetch = AsyncMock(return_value="Staff Engineer at BigCo")

        with patch("mkcv.core.services.jd_reader._fetch_url", mock_fetch):
            result = read_jd("https://example.com/jd")

        assert result == "Staff Engineer at BigCo"
        mock_fetch.assert_awaited_once_with("https://example.com/jd")

    def test_http_url_also_works(self) -> None:
        mock_fetch = AsyncMock(return_value="Engineer role")

        with patch("mkcv.core.services.jd_reader._fetch_url", mock_fetch):
            result = read_jd("http://example.com/jd")

        assert result == "Engineer role"
        mock_fetch.assert_awaited_once_with("http://example.com/jd")

    def test_http_error_raises_jd_read_error(self) -> None:
        mock_fetch = AsyncMock(
            side_effect=JDReadError(
                "Failed to fetch JD from URL (HTTP 404): https://example.com/missing"
            )
        )

        with (
            patch("mkcv.core.services.jd_reader._fetch_url", mock_fetch),
            pytest.raises(JDReadError, match="HTTP 404"),
        ):
            read_jd("https://example.com/missing")

    def test_connection_error_raises_jd_read_error(self) -> None:
        mock_fetch = AsyncMock(
            side_effect=JDReadError(
                "Failed to fetch JD from URL: https://unreachable.example.com/jd"
            )
        )

        with (
            patch("mkcv.core.services.jd_reader._fetch_url", mock_fetch),
            pytest.raises(JDReadError, match="Failed to fetch"),
        ):
            read_jd("https://unreachable.example.com/jd")

    def test_empty_url_response_raises_jd_read_error(self) -> None:
        mock_fetch = AsyncMock(
            side_effect=JDReadError(
                "JD fetched from URL is empty: https://example.com/empty"
            )
        )

        with (
            patch("mkcv.core.services.jd_reader._fetch_url", mock_fetch),
            pytest.raises(JDReadError, match="empty"),
        ):
            read_jd("https://example.com/empty")


# ------------------------------------------------------------------
# Test: _fetch_url (async unit tests)
# ------------------------------------------------------------------


class TestFetchURL:
    """Tests for the async _fetch_url helper."""

    async def test_fetch_url_returns_content(self) -> None:
        import httpx

        from mkcv.core.services.jd_reader import _fetch_url

        mock_response = httpx.Response(
            200,
            text="Staff Engineer at BigCo",
            request=httpx.Request("GET", "https://example.com/jd"),
        )

        async def mock_get(
            self: httpx.AsyncClient,
            url: str,
            **kwargs: object,
        ) -> httpx.Response:
            return mock_response

        with patch.object(httpx.AsyncClient, "get", mock_get):
            result = await _fetch_url("https://example.com/jd")

        assert result == "Staff Engineer at BigCo"

    async def test_fetch_url_http_error_raises(self) -> None:
        import httpx

        from mkcv.core.services.jd_reader import _fetch_url

        mock_response = httpx.Response(
            404,
            text="Not Found",
            request=httpx.Request("GET", "https://example.com/missing"),
        )

        async def mock_get(
            self: httpx.AsyncClient,
            url: str,
            **kwargs: object,
        ) -> httpx.Response:
            return mock_response

        with (
            patch.object(httpx.AsyncClient, "get", mock_get),
            pytest.raises(JDReadError, match="HTTP 404"),
        ):
            await _fetch_url("https://example.com/missing")

    async def test_fetch_url_connection_error_raises(self) -> None:
        import httpx

        from mkcv.core.services.jd_reader import _fetch_url

        async def mock_get(
            self: httpx.AsyncClient,
            url: str,
            **kwargs: object,
        ) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        with (
            patch.object(httpx.AsyncClient, "get", mock_get),
            pytest.raises(JDReadError, match="Failed to fetch"),
        ):
            await _fetch_url("https://unreachable.example.com/jd")

    async def test_fetch_url_empty_response_raises(self) -> None:
        import httpx

        from mkcv.core.services.jd_reader import _fetch_url

        mock_response = httpx.Response(
            200,
            text="",
            request=httpx.Request("GET", "https://example.com/empty"),
        )

        async def mock_get(
            self: httpx.AsyncClient,
            url: str,
            **kwargs: object,
        ) -> httpx.Response:
            return mock_response

        with (
            patch.object(httpx.AsyncClient, "get", mock_get),
            pytest.raises(JDReadError, match="empty"),
        ):
            await _fetch_url("https://example.com/empty")


# ------------------------------------------------------------------
# Test: stdin reads content
# ------------------------------------------------------------------


class TestReadJDFromStdin:
    """Tests for reading JD from stdin."""

    def test_reads_stdin_content(self) -> None:
        fake_stdin = io.StringIO("Platform Engineer at StartupCo")

        with patch("mkcv.core.services.jd_reader.sys.stdin", fake_stdin):
            result = read_jd("-")

        assert result == "Platform Engineer at StartupCo"

    def test_empty_string_source_reads_stdin(self) -> None:
        fake_stdin = io.StringIO("Backend Developer")

        with patch("mkcv.core.services.jd_reader.sys.stdin", fake_stdin):
            result = read_jd("")

        assert result == "Backend Developer"

    def test_tty_stdin_raises_jd_read_error(self) -> None:
        with (
            patch(
                "mkcv.core.services.jd_reader.sys.stdin.isatty",
                return_value=True,
            ),
            pytest.raises(JDReadError, match="No job description"),
        ):
            read_jd("-")

    def test_empty_stdin_raises_jd_read_error(self) -> None:
        fake_stdin = io.StringIO("")

        with (
            patch("mkcv.core.services.jd_reader.sys.stdin", fake_stdin),
            pytest.raises(JDReadError, match="empty"),
        ):
            read_jd("-")

    def test_whitespace_only_stdin_raises_jd_read_error(self) -> None:
        fake_stdin = io.StringIO("   \n\n  ")

        with (
            patch("mkcv.core.services.jd_reader.sys.stdin", fake_stdin),
            pytest.raises(JDReadError, match="empty"),
        ):
            read_jd("-")


# ------------------------------------------------------------------
# Test: JDReadError properties
# ------------------------------------------------------------------


class TestJDReadError:
    """Tests for JDReadError exception."""

    def test_exit_code_is_2(self) -> None:
        error = JDReadError("test")

        assert error.exit_code == 2

    def test_is_mkcv_error(self) -> None:
        from mkcv.core.exceptions.base import MkcvError

        error = JDReadError("test")

        assert isinstance(error, MkcvError)
