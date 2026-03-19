"""Tests for CoverLetterError exception."""

from mkcv.core.exceptions import CoverLetterError, MkcvError
from mkcv.core.exceptions.cover_letter import (
    CoverLetterError as DirectCoverLetterError,
)


class TestCoverLetterError:
    """Tests for CoverLetterError."""

    def test_exit_code_is_eight(self) -> None:
        err = CoverLetterError("cover letter failed")
        assert err.exit_code == 8

    def test_message_is_preserved(self) -> None:
        err = CoverLetterError("something went wrong")
        assert str(err) == "something went wrong"

    def test_inherits_from_mkcv_error(self) -> None:
        assert issubclass(CoverLetterError, MkcvError)

    def test_is_exception(self) -> None:
        assert issubclass(CoverLetterError, Exception)

    def test_importable_from_exceptions_package(self) -> None:
        assert CoverLetterError is DirectCoverLetterError

    def test_can_be_caught_as_mkcv_error(self) -> None:
        try:
            raise CoverLetterError("test")
        except MkcvError as exc:
            assert exc.exit_code == 8
