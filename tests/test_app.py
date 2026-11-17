"""Tests for the CLI wiring in app.py (spec 001, tasks T8 and T9).

The menus and the terminal check are stubbed: curses is only checked manually.
"""

import curses
import logging
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from ft_otp import app
from ft_otp.constants import CANCEL, ERASE, KEEP, NO, REPLACE, YES
from ft_otp.secret import check_secret, create_secret

HEX_64 = "0123456789abcdef" * 4
SEED = bytes.fromhex(HEX_64)


@pytest.fixture(autouse=True)
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Run every test in tmp_path, with the secret file in tmp_path too."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app, "PROJECT_ROOT", tmp_path)
    root = logging.getLogger()
    saved = (root.handlers[:], root.level)
    yield tmp_path
    root.handlers[:] = saved[0]
    root.setLevel(saved[1])


def stub(
    monkeypatch: pytest.MonkeyPatch, interactive: bool, choices: list[str] | None = None
) -> list[tuple[str, str]]:
    """Stub the terminal check and the menus; return the menus that were shown."""
    shown: list[tuple[str, str]] = []
    answers = list(choices or [])

    def run_menu(name: str, details: str = "") -> str:
        shown.append((name, details))
        return answers.pop(0)

    monkeypatch.setattr(app, "is_interactive", lambda: interactive)
    monkeypatch.setattr(app, "run_menu", run_menu)
    return shown


def key_file(tmp_path: Path, content: str = HEX_64 + "\n") -> Path:
    path = tmp_path / "key.hex"
    path.write_text(content)
    return path


def stored_seed(tmp_path: Path) -> bytes:
    secret = check_secret(tmp_path / ".env")
    return Fernet(secret).decrypt((tmp_path / "ft_otp.key").read_bytes())


Capture = pytest.CaptureFixture[str]


# ---- T8: -g (FR-9, FR-11, FR-12, FR-14, FR-32, FR-33, NFR-1, NFR-3) -------------


def test_store_new_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture) -> None:
    shown = stub(monkeypatch, interactive=True)
    assert app.main(["-g", str(key_file(tmp_path))]) == 0
    out, err = capsys.readouterr()
    assert "stored" in out and "clear text" in out
    assert err == ""
    assert shown == []
    assert stored_seed(tmp_path) == SEED


def test_store_writes_in_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    stub(monkeypatch, interactive=True)
    assert app.main(["-g", str(key_file(tmp_path))]) == 0
    assert (work / "ft_otp.key").exists()
    assert (tmp_path / ".env").exists()


def test_existing_key_without_terminal_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    (tmp_path / "ft_otp.key").write_bytes(b"old")
    shown = stub(monkeypatch, interactive=False)
    assert app.main(["-g", str(key_file(tmp_path))]) == 1
    out, err = capsys.readouterr()
    assert "already exists" in err
    assert shown == []
    assert (tmp_path / "ft_otp.key").read_bytes() == b"old"


def test_existing_key_kept_when_user_chooses_keep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    (tmp_path / "ft_otp.key").write_bytes(b"old")
    shown = stub(monkeypatch, interactive=True, choices=[KEEP])
    assert app.main(["-g", str(key_file(tmp_path))]) == 0
    out, _ = capsys.readouterr()
    assert "already exists" in out
    assert [name for name, _ in shown] == ["key_exists"]
    assert (tmp_path / "ft_otp.key").read_bytes() == b"old"


def test_existing_key_replaced_when_user_confirms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    (tmp_path / "ft_otp.key").write_bytes(b"old")
    stub(monkeypatch, interactive=True, choices=[REPLACE])
    assert app.main(["-g", str(key_file(tmp_path))]) == 0
    out, _ = capsys.readouterr()
    assert "stored" in out
    assert stored_seed(tmp_path) == SEED


def test_invalid_key_is_reported_without_menu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    (tmp_path / "ft_otp.key").write_bytes(b"old")
    shown = stub(monkeypatch, interactive=True, choices=[REPLACE])
    assert app.main(["-g", str(key_file(tmp_path, "not hex"))]) == 1
    out, err = capsys.readouterr()
    assert err.startswith("ft_otp: error:") and "hexadecimal" in err
    assert out == ""
    assert shown == []


def test_missing_key_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture) -> None:
    stub(monkeypatch, interactive=True)
    assert app.main(["-g", str(tmp_path / "missing.hex")]) == 1
    assert "not found" in capsys.readouterr().err


@pytest.mark.parametrize("debug", [[], ["--debug"]])
def test_output_never_contains_seed_or_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture, debug: list[str]
) -> None:
    (tmp_path / "ft_otp.key").write_bytes(b"old")
    stub(monkeypatch, interactive=True, choices=[REPLACE])
    assert app.main(["-g", str(key_file(tmp_path)), *debug]) == 0
    out, err = capsys.readouterr()
    secret = check_secret(tmp_path / ".env").decode()
    for text in (out, err):
        assert HEX_64 not in text.lower()
        assert secret not in text


def test_is_interactive_needs_both_stdin_and_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    class Stream:
        def __init__(self, tty: bool) -> None:
            self.tty = tty

        def isatty(self) -> bool:
            return self.tty

    checks: list[tuple[bool, bool, bool]] = [
        (True, True, True),
        (True, False, False),
        (False, True, False),
    ]
    for stdin, stdout, expected in checks:
        monkeypatch.setattr(app.sys, "stdin", Stream(stdin))
        monkeypatch.setattr(app.sys, "stdout", Stream(stdout))
        assert app.is_interactive() is expected
    monkeypatch.undo()


# ---- T9: --reset (FR-35 to FR-40, FR-44, FR-45, FR-48, FR-49) ------------------


def both_files(tmp_path: Path) -> None:
    (tmp_path / "ft_otp.key").write_bytes(b"old")
    create_secret(tmp_path / ".env")


@pytest.mark.parametrize("with_files", [True, False])
def test_reset_needs_terminal_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture, with_files: bool
) -> None:
    if with_files:
        both_files(tmp_path)
    shown = stub(monkeypatch, interactive=False)
    assert app.main(["--reset"]) == 1
    assert "interactive terminal" in capsys.readouterr().err
    assert shown == []
    assert (tmp_path / ".env").exists() is with_files


def test_reset_nothing_to_reset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    shown = stub(monkeypatch, interactive=True)
    assert app.main(["--reset"]) == 0
    assert "nothing to reset" in capsys.readouterr().out.lower()
    assert shown == []


@pytest.mark.parametrize("choices", [[CANCEL], [ERASE, NO]], ids=["menu", "are-you-sure"])
def test_reset_cancelled_erases_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture, choices: list[str]
) -> None:
    both_files(tmp_path)
    shown = stub(monkeypatch, interactive=True, choices=choices)
    assert app.main(["--reset"]) == 0
    assert "cancelled" in capsys.readouterr().out.lower()
    assert len(shown) == len(choices)
    assert (tmp_path / "ft_otp.key").exists() and (tmp_path / ".env").exists()


def test_reset_menu_details_list_files_and_warn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "ft_otp.key").mkdir()
    create_secret(tmp_path / ".env")
    shown = stub(monkeypatch, interactive=True, choices=[CANCEL])
    app.main(["--reset"])
    name, details = shown[0]
    assert name == "reset"
    assert str(tmp_path / ".env") in details
    assert str(tmp_path / "ft_otp.key") in details
    assert "permanently unusable" in details
    assert "directories are never erased" in details.lower()
    assert "manually" in details


def test_reset_confirmed_erases_both(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    both_files(tmp_path)
    shown = stub(monkeypatch, interactive=True, choices=[ERASE, YES])
    assert app.main(["--reset"]) == 0
    out, err = capsys.readouterr()
    assert [name for name, _ in shown] == ["reset", "confirm"]
    assert out.count("erased") == 2 and err == ""
    assert not (tmp_path / "ft_otp.key").exists()
    assert not (tmp_path / ".env").exists()


def test_reset_reports_absent_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    create_secret(tmp_path / ".env")
    stub(monkeypatch, interactive=True, choices=[ERASE, YES])
    assert app.main(["--reset"]) == 0
    out, _ = capsys.readouterr()
    assert "already absent" in out
    assert not (tmp_path / ".env").exists()


def test_reset_directory_is_reported_and_other_erased(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    (tmp_path / "ft_otp.key").mkdir()
    create_secret(tmp_path / ".env")
    stub(monkeypatch, interactive=True, choices=[ERASE, YES])
    assert app.main(["--reset"]) == 1
    out, err = capsys.readouterr()
    assert "manually" in err
    assert (tmp_path / "ft_otp.key").is_dir()
    assert not (tmp_path / ".env").exists()


def test_reset_erase_failure_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    both_files(tmp_path)
    stub(monkeypatch, interactive=True, choices=[ERASE, YES])
    real_unlink = os.unlink

    def unlink(path: object, *args: object, **kwargs: object) -> None:
        if Path(path).name == "ft_otp.key":
            raise PermissionError(13, "Permission denied")
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", unlink)
    result = app.main(["--reset"])
    monkeypatch.setattr(os, "unlink", real_unlink)
    assert result == 1
    assert "Permission denied" in capsys.readouterr().err
    assert not (tmp_path / ".env").exists()


# ---- Fix 1 (VERIFICATION.md): a menu that cannot be drawn (constitution 6) -----


def failing_menu(monkeypatch: pytest.MonkeyPatch, fail_on: str, choices: list[str]) -> None:
    """Stub run_menu so the menu `fail_on` raises curses.error (terminal too small)."""
    answers = list(choices)

    def run_menu(name: str, details: str = "") -> str:
        if name == fail_on:
            raise curses.error("addwstr() returned ERR")
        return answers.pop(0)

    monkeypatch.setattr(app, "is_interactive", lambda: True)
    monkeypatch.setattr(app, "run_menu", run_menu)


def test_store_menu_too_small_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    (tmp_path / "ft_otp.key").write_bytes(b"old")
    failing_menu(monkeypatch, "key_exists", [])
    assert app.main(["-g", str(key_file(tmp_path))]) == 1
    out, err = capsys.readouterr()
    assert err.startswith("ft_otp: error:") and "too small" in err
    assert (tmp_path / "ft_otp.key").read_bytes() == b"old"


@pytest.mark.parametrize(("fail_on", "choices"), [("reset", []), ("confirm", [ERASE])])
def test_reset_menu_too_small_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Capture,
    fail_on: str,
    choices: list[str],
) -> None:
    both_files(tmp_path)
    failing_menu(monkeypatch, fail_on, choices)
    assert app.main(["--reset"]) == 1
    out, err = capsys.readouterr()
    assert err.startswith("ft_otp: error:") and "too small" in err
    assert (tmp_path / "ft_otp.key").exists() and (tmp_path / ".env").exists()
