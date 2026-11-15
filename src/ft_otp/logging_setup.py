"""Logging configuration."""

import logging

DEBUG_FORMAT = "%(levelname)s: %(message)s [%(filename)s:%(lineno)d]"


def setup_logging(debug: bool) -> None:
    """Configure the root logger: DEBUG with file/line info, or INFO."""
    if debug:
        logging.basicConfig(level=logging.DEBUG, format=DEBUG_FORMAT)
    else:
        logging.basicConfig(level=logging.INFO)
