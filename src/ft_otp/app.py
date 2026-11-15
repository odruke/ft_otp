"""Program entry point: wires the CLI options to the right action."""

import subprocess
import sys
from collections.abc import Sequence

from ft_otp.cli import parse_arguments
from ft_otp.constants import PROJECT_ROOT
from ft_otp.logging_setup import setup_logging
from ft_otp.menu import run_menu


def run_tests() -> int:
    """Run the test suite with pytest and return its exit code."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest"],
        cwd=PROJECT_ROOT,
        check=False,
    )
    return result.returncode


def main(argv: Sequence[str] | None = None) -> int:
    """Run ft_otp and return the process exit code."""
    options = parse_arguments(argv)
    setup_logging(options.debug)

    if options.run_tests:
        return run_tests()

    run_menu("base")  # only option for now is EXIT
    return 0
