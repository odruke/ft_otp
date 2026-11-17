"""Tests for the stdout/stderr logging split (constitution 6, task T7)."""

import logging
from collections.abc import Iterator

import pytest

from ft_otp.logging_setup import setup_logging


@pytest.fixture(autouse=True)
def clean_root_logger() -> Iterator[None]:
    root = logging.getLogger()
    saved = (root.handlers[:], root.level)
    root.handlers.clear()
    yield
    root.handlers[:] = saved[0]
    root.setLevel(saved[1])


def test_info_goes_to_stdout_as_bare_message(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging(debug=False)
    logging.getLogger("ft_otp.test").info("Key stored.")
    out, err = capsys.readouterr()
    assert out == "Key stored.\n"
    assert err == ""


def test_error_goes_to_stderr_with_prefix(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging(debug=False)
    logging.getLogger("ft_otp.test").error("file not found.")
    out, err = capsys.readouterr()
    assert out == ""
    assert err == "ft_otp: error: file not found.\n"


def test_debug_hidden_unless_enabled(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging(debug=False)
    logging.getLogger("ft_otp.test").debug("details")
    assert capsys.readouterr() == ("", "")


def test_debug_mode_shows_debug_records(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging(debug=True)
    logging.getLogger("ft_otp.test").debug("details")
    out, _ = capsys.readouterr()
    assert "details" in out
