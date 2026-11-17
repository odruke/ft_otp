"""Program entry point: wires the CLI options to the right action."""

import curses
import logging
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from ft_otp.cli import Options, parse_arguments
from ft_otp.constants import ERASE, PROJECT_ROOT, REPLACE, YES
from ft_otp.errors import KeyManagerError
from ft_otp.key_manager import (
    KEY_FILE_NAME,
    KeyManager,
    PathKind,
    ResetOutcome,
)
from ft_otp.logging_setup import setup_logging
from ft_otp.menu import run_menu

logger = logging.getLogger(__name__)

SECRET_FILE_NAME = ".env"
MENU_TOO_SMALL = (
    "The terminal is too small to show the menu; nothing was changed. "
    "Enlarge the window and try again."
)


def run_tests() -> int:
    """Run the test suite with pytest and return its exit code."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest"],
        cwd=PROJECT_ROOT,
        check=False,
    )
    return result.returncode


def is_interactive() -> bool:
    """True if menus can be shown: both stdin and stdout are terminals."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def key_manager() -> KeyManager:
    """ft_otp.key in the current directory, the secret in the project."""
    return KeyManager(
        Path.cwd() / KEY_FILE_NAME, PROJECT_ROOT / SECRET_FILE_NAME
    )


def store_key(options: Options) -> int:
    """-g FILE: validate the key file and store it encrypted in ft_otp.key."""
    manager = key_manager()
    try:
        prepared = manager.prepare(Path(options.key_to_store))
        if prepared.stored_key_exists:
            if not is_interactive():
                logger.error(
                    f"{KEY_FILE_NAME} already exists and was kept: "
                    "replacing it needs an interactive terminal."
                )
                return 1
            if run_menu("key_exists") != REPLACE:
                logger.info(f"{KEY_FILE_NAME} already exists and was kept.")
                return 0
        manager.save(prepared.seed, replace=prepared.stored_key_exists)
    except KeyManagerError as e:
        logger.error(e)
        return 1
    except curses.error:
        logger.error(MENU_TOO_SMALL)
        return 1
    logger.info(f"Key stored in {KEY_FILE_NAME}.")
    logger.info(
        f"Reminder: {options.key_to_store} still contains the key in clear "
        "text; delete it if you no longer need it."
    )
    return 0


def reset_details(status: dict[Path, PathKind]) -> str:
    """Text shown above the reset menu: existing files and the warning."""
    existing = [
        str(path)
        for path, kind in status.items()
        if kind is not PathKind.ABSENT
    ]
    lines = ["Existing files: " + ", ".join(existing), ""]
    lines.append(
        f"The reset erases both {KEY_FILE_NAME} and the secret file "
        f"({SECRET_FILE_NAME}): without the secret, every stored key file is "
        "permanently unusable. Directories are never erased."
    )
    for path, kind in status.items():
        if kind is PathKind.DIRECTORY:
            lines.append(
                f"{path} is a directory: it will not be erased, "
                "fix it manually."
            )
    return "\n".join(lines) + "\n\n"


def reset() -> int:
    """--reset: erase ft_otp.key and the secret file, after confirmation."""
    if not is_interactive():
        logger.error(
            "A reset needs an interactive terminal; nothing was erased."
        )
        return 1
    manager = key_manager()
    status = manager.reset_status()
    if all(kind is PathKind.ABSENT for kind in status.values()):
        logger.info("Nothing to reset: neither file exists.")
        return 0
    try:
        confirmed = (
            run_menu("reset", reset_details(status)) == ERASE
            and run_menu("confirm") == YES
        )
    except curses.error:
        logger.error(MENU_TOO_SMALL)
        return 1
    if not confirmed:
        logger.info("Reset cancelled; nothing was erased.")
        return 0
    failed = False
    for result in manager.reset():
        if result.outcome is ResetOutcome.ERASED:
            logger.info(f"{result.path}: erased.")
        elif result.outcome is ResetOutcome.ABSENT:
            logger.info(f"{result.path}: already absent.")
        else:
            logger.error(result.error)
            failed = True
    return 1 if failed else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run ft_otp and return the process exit code."""
    options = parse_arguments(argv)
    setup_logging(options.debug)

    if options.run_tests:
        return run_tests()
    if options.key_to_store:
        return store_key(options)
    if options.reset:
        return reset()
    return 0
