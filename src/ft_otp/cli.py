"""Command-line argument parsing."""

import argparse
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Options:
    """Parsed command-line options."""

    key_to_store: str | None
    key_file: str | None
    interface: bool
    run_tests: bool
    debug: bool


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for ft_otp."""
    parser = argparse.ArgumentParser(
        prog="ft_otp",
        description="Generate time-based one-time passwords (TOTP).",
    )
    parser.add_argument(
        "-g",
        "--generate",
        metavar="FILE",
        help="store the 64 hex character key from FILE, encrypted, in ft_otp.key",
    )
    parser.add_argument(
        "-k",
        "--key",
        metavar="FILE",
        help="print a one-time password generated from the key in FILE",
    )
    parser.add_argument(
        "-i",
        "--interface",
        action="store_true",
        help="launch the graphical interface",
    )
    parser.add_argument(
        "-t",
        "--run-tests",
        action="store_true",
        help="run the test suite",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="enable verbose debug logging",
    )
    return parser


def parse_arguments(argv: Sequence[str] | None = None) -> Options:
    """Parse argv (defaults to sys.argv[1:]) into an Options object."""
    args = build_parser().parse_args(argv)
    return Options(
        key_to_store=args.generate,
        key_file=args.key,
        interface=args.interface,
        run_tests=args.run_tests,
        debug=args.debug,
    )
