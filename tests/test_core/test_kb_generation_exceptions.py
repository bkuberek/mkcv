"""Tests for KB generation exception classes."""

from mkcv.core.exceptions.base import MkcvError
from mkcv.core.exceptions.kb_generation import DocumentReadError, KBGenerationError


class TestKBGenerationError:
    """Tests for KBGenerationError."""

    def test_exit_code_is_nine(self) -> None:
        err = KBGenerationError("generation failed")
        assert err.exit_code == 9

    def test_message_is_preserved(self) -> None:
        err = KBGenerationError("something broke")
        assert str(err) == "something broke"

    def test_inherits_from_mkcv_error(self) -> None:
        assert issubclass(KBGenerationError, MkcvError)

    def test_is_exception(self) -> None:
        assert issubclass(KBGenerationError, Exception)


class TestDocumentReadError:
    """Tests for DocumentReadError."""

    def test_exit_code_is_nine(self) -> None:
        err = DocumentReadError("cannot read file")
        assert err.exit_code == 9

    def test_message_is_preserved(self) -> None:
        err = DocumentReadError("bad file format")
        assert str(err) == "bad file format"

    def test_inherits_from_mkcv_error(self) -> None:
        assert issubclass(DocumentReadError, MkcvError)

    def test_is_exception(self) -> None:
        assert issubclass(DocumentReadError, Exception)
