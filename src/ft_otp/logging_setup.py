"""Logging configuration: every interface message goes through logging.

Records below WARNING (results, information) go to stdout as the bare message;
WARNING and above go to stderr as "ft_otp: <level>: <message>".
"""

import logging
import sys

DEBUG_FORMAT = "%(levelname)s: %(message)s [%(filename)s:%(lineno)d]"


class ProblemFormatter(logging.Formatter):
    """Format warnings and errors as 'ft_otp: error: message'."""

    def format(self, record: logging.LogRecord) -> str:
        return f"ft_otp: {record.levelname.lower()}: {record.getMessage()}"


def setup_logging(debug: bool) -> None:
    """Configure the root logger: DEBUG with file/line info, or INFO."""
    stdout = logging.StreamHandler(sys.stdout)
    stdout.addFilter(lambda record: record.levelno < logging.WARNING)
    stderr = logging.StreamHandler(sys.stderr)
    stderr.setLevel(logging.WARNING)
    if debug:
        stdout.setFormatter(logging.Formatter(DEBUG_FORMAT))
        stderr.setFormatter(logging.Formatter(DEBUG_FORMAT))
    else:
        stdout.setFormatter(logging.Formatter("%(message)s"))
        stderr.setFormatter(ProblemFormatter())
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        handlers=[stdout, stderr],
        force=True,
    )
