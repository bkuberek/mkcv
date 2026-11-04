"""Tests for the harness's logging setup."""

import logging

import pytest

from evals.harness.logging_setup import configure_logging


@pytest.fixture(autouse=True)
def _restore_loggers() -> object:
    names = ("mkcv", "evals")
    saved = {
        name: (logging.getLogger(name).level, list(logging.getLogger(name).handlers))
        for name in names
    }
    yield
    for name, (level, handlers) in saved.items():
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.handlers[:] = handlers


def test_an_mkcv_warning_goes_to_stderr_with_its_logger_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging()
    logging.getLogger("mkcv.adapters.llm.retry").warning("retrying in 2s")
    assert (
        capsys.readouterr().err == "WARNING mkcv.adapters.llm.retry: retrying in 2s\n"
    )


def test_an_evals_warning_goes_to_stderr_too(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging()
    logging.getLogger("evals.harness.stage_runner").warning("careful")
    assert "careful" in capsys.readouterr().err


def test_info_messages_are_hidden_by_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging()
    logging.getLogger("evals.harness.stage_runner").info("Running x")
    assert capsys.readouterr().err == ""


def test_verbose_shows_info_messages(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(verbose=True)
    logging.getLogger("evals.harness.stage_runner").info("Running x")
    assert "Running x" in capsys.readouterr().err


def test_calling_it_twice_does_not_repeat_messages(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging()
    configure_logging()
    logging.getLogger("mkcv.x").warning("once")
    assert capsys.readouterr().err.count("once") == 1


def test_a_later_call_follows_the_current_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging()
    logging.getLogger("mkcv.x").warning("first")
    capsys.readouterr()
    configure_logging()
    logging.getLogger("mkcv.x").warning("second")
    assert "second" in capsys.readouterr().err


def test_verbose_does_not_open_up_other_libraries(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(verbose=True)
    logging.getLogger("httpx").info("HTTP Request: POST https://api.example.com")
    assert capsys.readouterr().err == ""
