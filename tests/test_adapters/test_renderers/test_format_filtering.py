"""Tests for format filtering in RenderCVAdapter."""

import pytest

from mkcv.adapters.renderers.rendercv import (
    ALL_FORMATS,
    _normalize_formats,
)
from mkcv.core.exceptions.render import RenderError


class TestNormalizeFormats:
    """Tests for the _normalize_formats helper."""

    def test_none_returns_all_formats(self) -> None:
        result = _normalize_formats(None)
        assert result == ALL_FORMATS

    def test_single_format(self) -> None:
        result = _normalize_formats(["pdf"])
        assert result == frozenset({"pdf"})

    def test_multiple_formats(self) -> None:
        result = _normalize_formats(["pdf", "png"])
        assert result == frozenset({"pdf", "png"})

    def test_all_four_formats(self) -> None:
        result = _normalize_formats(["pdf", "png", "md", "html"])
        assert result == ALL_FORMATS

    def test_case_insensitive(self) -> None:
        result = _normalize_formats(["PDF", "Png"])
        assert result == frozenset({"pdf", "png"})

    def test_strips_whitespace(self) -> None:
        result = _normalize_formats([" pdf ", " png"])
        assert result == frozenset({"pdf", "png"})

    def test_unknown_format_raises_render_error(self) -> None:
        with pytest.raises(RenderError, match="Unknown output format"):
            _normalize_formats(["pdf", "docx"])

    def test_error_lists_unknown_formats(self) -> None:
        with pytest.raises(RenderError, match="docx"):
            _normalize_formats(["docx"])

    def test_error_lists_supported_formats(self) -> None:
        with pytest.raises(RenderError, match="Supported:"):
            _normalize_formats(["odt"])
