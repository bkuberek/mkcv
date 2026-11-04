"""Show mkcv's and the harness's log messages on stderr, in one format."""

import logging
import sys

LOG_FORMAT = "%(levelname)s %(name)s: %(message)s"
LOGGER_NAMES = ("mkcv", "evals")
_HANDLER_MARK = "_evals_handler"


def configure_logging(*, verbose: bool = False) -> None:
    """Send ``mkcv`` and ``evals`` log records to stderr.

    Warnings and errors always show (retries, YAML repairs, provider fallbacks);
    ``verbose`` adds the info messages, such as each stage run starting. Other
    libraries (``httpx`` and the provider SDKs) are left at their defaults.
    Calling it again replaces the handler, so messages never repeat.
    """
    level = logging.INFO if verbose else logging.WARNING
    for name in LOGGER_NAMES:
        logger = logging.getLogger(name)
        for handler in list(logger.handlers):
            if getattr(handler, _HANDLER_MARK, False):
                logger.removeHandler(handler)
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        setattr(handler, _HANDLER_MARK, True)
        logger.addHandler(handler)
        logger.setLevel(level)
