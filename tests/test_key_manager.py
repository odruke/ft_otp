"""Tests for the KeyManager core (spec 001)."""

import os
import stat
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from ft_otp.errors import (
    EraseError,
    InvalidKeyError,
    KeyExistsError,
    KeyFileNotFoundError,
    KeyManagerError,
    SecretError,
    UnsupportedFileError,
    WriteError,
)
from ft_otp.key_manager import KeyManager, PathKind, ResetOutcome
from ft_otp.secret import check_secret, create_secret

HEX_64 = "0123456789abcdef" * 4  # 64 lowercase hex digits


# ---- T1: parse_hex (FR-1 to FR-6, FR-30) ------------------------------------


@pytest.mark.parametrize("length", [64, 128, 1024])
def test_parse_hex_accepts_valid_lengths(length: int) -> None:
    text = ("ab" * length)[:length]
    assert KeyManager.parse_hex(text) == bytes.fromhex(text)


@pytest.mark.parametrize("length", [0, 62, 1026])
def test_parse_hex_rejects_out_of_range_even_lengths(length: int) -> None:
    with pytest.raises(InvalidKeyError, match="64"):
        KeyManager.parse_hex("a" * length)


@pytest.mark.parametrize("length", [63, 65, 1025])
def test_parse_hex_rejects_odd_lengths(length: int) -> None:
    with pytest.raises(InvalidKeyError, match="even"):
        KeyManager.parse_hex("a" * length)


def test_parse_hex_strips_surrounding_unicode_whitespace() -> None:
    text = "　\t \n" + HEX_64 + "\r\n "
    assert KeyManager.parse_hex(text) == bytes.fromhex(HEX_64)


@pytest.mark.parametrize(
    "text",
    [
        HEX_64[:32] + " " + HEX_64[32:],  # inner space
        HEX_64[:32] + "\r\n" + HEX_64[32:],  # inner line break
        "0x" + HEX_64,  # prefix
        "﻿" + HEX_64,  # UTF-8 byte-order mark is not whitespace
        HEX_64[:-1] + "g",  # non-hex letter
    ],
)
def test_parse_hex_rejects_non_hex_characters(text: str) -> None:
    with pytest.raises(InvalidKeyError, match="hexadecimal"):
        KeyManager.parse_hex(text)


def test_parse_hex_reports_only_first_broken_rule() -> None:
    # Non-hex, odd and too short at once: non-hex comes first (FR-30).
    with pytest.raises(InvalidKeyError, match="hexadecimal"):
        KeyManager.parse_hex("xyz")
    # Odd and too short: odd comes before length.
    with pytest.raises(InvalidKeyError, match="even"):
        KeyManager.parse_hex("abc")


def test_parse_hex_is_case_insensitive() -> None:
    assert KeyManager.parse_hex(HEX_64.upper()) == KeyManager.parse_hex(HEX_64)


def test_invalid_key_error_is_a_key_manager_error() -> None:
    assert issubclass(InvalidKeyError, KeyManagerError)


def test_error_message_never_contains_the_key() -> None:
    with pytest.raises(InvalidKeyError) as excinfo:
        KeyManager.parse_hex(HEX_64 + "a")
    assert HEX_64 not in str(excinfo.value)


# ---- T2: read_key_file (FR-7, FR-8, FR-15, FR-27, FR-28, FR-29, FR-41) -------

IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0
HEX_1024 = "ab" * 512


def write(path: Path, data: bytes | str, mode: int = 0o600) -> Path:
    if isinstance(data, str):
        data = data.encode()
    path.write_bytes(data)
    path.chmod(mode)
    return path


def test_read_key_file_returns_seed(tmp_path: Path) -> None:
    key = write(tmp_path / "key.hex", HEX_64 + "\n")
    assert KeyManager.read_key_file(key) == bytes.fromhex(HEX_64)


def test_read_key_file_missing(tmp_path: Path) -> None:
    with pytest.raises(KeyFileNotFoundError):
        KeyManager.read_key_file(tmp_path / "missing.hex")


def test_read_key_file_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedFileError, match="regular"):
        KeyManager.read_key_file(tmp_path)


def test_read_key_file_rejects_device() -> None:
    with pytest.raises(UnsupportedFileError, match="regular"):
        KeyManager.read_key_file(Path("/dev/null"))


def test_read_key_file_rejects_named_pipe_without_blocking(tmp_path: Path) -> None:
    pipe = tmp_path / "pipe"
    os.mkfifo(pipe)
    with pytest.raises(UnsupportedFileError, match="regular"):
        KeyManager.read_key_file(pipe)


def test_read_key_file_rejects_symlink_to_valid_key(tmp_path: Path) -> None:
    target = write(tmp_path / "key.hex", HEX_64)
    link = tmp_path / "link.hex"
    link.symlink_to(target)
    with pytest.raises(UnsupportedFileError, match="regular"):
        KeyManager.read_key_file(link)


def test_read_key_file_rejects_broken_symlink(tmp_path: Path) -> None:
    link = tmp_path / "link.hex"
    link.symlink_to(tmp_path / "nowhere")
    with pytest.raises(UnsupportedFileError, match="regular"):
        KeyManager.read_key_file(link)


def test_read_key_file_accepts_1024_digits_and_newline(tmp_path: Path) -> None:
    key = write(tmp_path / "key.hex", HEX_1024 + "\n")  # 1025 bytes
    assert KeyManager.read_key_file(key) == bytes.fromhex(HEX_1024)


def test_read_key_file_rejects_1024_digits_and_crlf(tmp_path: Path) -> None:
    key = write(tmp_path / "key.hex", HEX_1024 + "\r\n")  # 1026 bytes
    with pytest.raises(UnsupportedFileError, match="too large"):
        KeyManager.read_key_file(key)


def test_read_key_file_too_large_checked_before_utf8(tmp_path: Path) -> None:
    key = write(tmp_path / "key.bin", b"\xff" * 2000)
    with pytest.raises(UnsupportedFileError, match="too large"):
        KeyManager.read_key_file(key)


def test_read_key_file_rejects_invalid_utf8(tmp_path: Path) -> None:
    key = write(tmp_path / "key.bin", b"\xff\xfe" + HEX_64.encode())
    with pytest.raises(UnsupportedFileError, match="read"):
        KeyManager.read_key_file(key)


@pytest.mark.skipif(IS_ROOT, reason="root ignores file permissions")
def test_read_key_file_rejects_unreadable_file(tmp_path: Path) -> None:
    key = write(tmp_path / "key.hex", HEX_64, mode=0o000)
    with pytest.raises(UnsupportedFileError, match="read"):
        KeyManager.read_key_file(key)


def test_read_key_file_ignores_permissions(tmp_path: Path) -> None:
    key = write(tmp_path / "key.hex", HEX_64, mode=0o644)
    assert KeyManager.read_key_file(key) == bytes.fromhex(HEX_64)


def test_read_key_file_content_errors_come_after_file_checks(tmp_path: Path) -> None:
    key = write(tmp_path / "key.hex", "not hex")
    with pytest.raises(InvalidKeyError):
        KeyManager.read_key_file(key)


def test_read_key_file_leaves_input_untouched(tmp_path: Path) -> None:
    key = write(tmp_path / "key.hex", HEX_64 + "\n", mode=0o644)
    before = key.stat()
    KeyManager.read_key_file(key)
    after = key.stat()
    assert key.read_text() == HEX_64 + "\n"
    assert (after.st_mtime_ns, after.st_mode) == (before.st_mtime_ns, before.st_mode)


# ---- T4: prepare (FR-11, FR-20, FR-31, FR-42, FR-43) --------------------------


def make_manager(tmp_path: Path) -> KeyManager:
    return KeyManager(tmp_path / "ft_otp.key", tmp_path / ".env")


def test_stored_key_exists_false_when_absent(tmp_path: Path) -> None:
    assert make_manager(tmp_path).stored_key_exists() is False


def test_stored_key_exists_true_for_regular_file(tmp_path: Path) -> None:
    write(tmp_path / "ft_otp.key", b"anything, never read", mode=0o644)
    assert make_manager(tmp_path).stored_key_exists() is True


def test_stored_key_exists_rejects_directory(tmp_path: Path) -> None:
    (tmp_path / "ft_otp.key").mkdir()
    with pytest.raises(UnsupportedFileError, match="regular"):
        make_manager(tmp_path).stored_key_exists()


def test_stored_key_exists_rejects_symlink(tmp_path: Path) -> None:
    target = write(tmp_path / "elsewhere", b"x")
    (tmp_path / "ft_otp.key").symlink_to(target)
    with pytest.raises(UnsupportedFileError, match="regular"):
        make_manager(tmp_path).stored_key_exists()


def test_prepare_returns_seed_and_flag(tmp_path: Path) -> None:
    key = write(tmp_path / "key.hex", HEX_64)
    prepared = make_manager(tmp_path).prepare(key)
    assert prepared.seed == bytes.fromhex(HEX_64)
    assert prepared.stored_key_exists is False

    write(tmp_path / "ft_otp.key", b"old")
    assert make_manager(tmp_path).prepare(key).stored_key_exists is True


def test_prepare_reports_invalid_key_before_broken_secret(tmp_path: Path) -> None:
    key = write(tmp_path / "key.hex", "not hex")
    write(tmp_path / ".env", b"garbage", mode=0o644)
    with pytest.raises(InvalidKeyError):
        make_manager(tmp_path).prepare(key)


def test_prepare_reports_broken_secret_before_existing_key(tmp_path: Path) -> None:
    key = write(tmp_path / "key.hex", HEX_64)
    write(tmp_path / ".env", b"garbage")
    write(tmp_path / "ft_otp.key", b"old")
    with pytest.raises(SecretError):
        make_manager(tmp_path).prepare(key)


def test_prepare_reports_broken_secret_before_non_regular_key(tmp_path: Path) -> None:
    key = write(tmp_path / "key.hex", HEX_64)
    write(tmp_path / ".env", b"garbage")
    (tmp_path / "ft_otp.key").mkdir()
    with pytest.raises(SecretError):
        make_manager(tmp_path).prepare(key)


def test_prepare_never_creates_files(tmp_path: Path) -> None:
    key = write(tmp_path / "key.hex", HEX_64)
    make_manager(tmp_path).prepare(key)
    assert not (tmp_path / ".env").exists()
    assert not (tmp_path / "ft_otp.key").exists()


def test_prepared_key_repr_hides_seed(tmp_path: Path) -> None:
    key = write(tmp_path / "key.hex", HEX_64)
    prepared = make_manager(tmp_path).prepare(key)
    text = repr(prepared)
    assert HEX_64 not in text and repr(prepared.seed) not in text


# ---- T5: save (FR-9, FR-10, FR-12, FR-13, FR-16, FR-17, FR-20, FR-32, FR-34) ---

SEED = bytes.fromhex(HEX_64)


def mode_of(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def decrypt_stored(tmp_path: Path) -> bytes:
    secret = check_secret(tmp_path / ".env")
    return Fernet(secret).decrypt((tmp_path / "ft_otp.key").read_bytes())


def leftovers(tmp_path: Path) -> list[str]:
    return [p.name for p in tmp_path.iterdir() if p.name.startswith(".ft_otp.key.")]


def test_save_new_key(tmp_path: Path) -> None:
    make_manager(tmp_path).save(SEED)
    assert decrypt_stored(tmp_path) == SEED
    assert mode_of(tmp_path / "ft_otp.key") == 0o600
    assert mode_of(tmp_path / ".env") == 0o600
    assert leftovers(tmp_path) == []


def test_save_existing_key_without_replace(tmp_path: Path) -> None:
    write(tmp_path / "ft_otp.key", b"old")
    with pytest.raises(KeyExistsError):
        make_manager(tmp_path).save(SEED)
    assert (tmp_path / "ft_otp.key").read_bytes() == b"old"
    assert not (tmp_path / ".env").exists()


def test_save_replace_writes_owner_only_file(tmp_path: Path) -> None:
    write(tmp_path / "ft_otp.key", b"old", mode=0o644)
    make_manager(tmp_path).save(SEED, replace=True)
    assert decrypt_stored(tmp_path) == SEED
    assert mode_of(tmp_path / "ft_otp.key") == 0o600


def test_save_reuses_existing_secret(tmp_path: Path) -> None:
    secret = create_secret(tmp_path / ".env")
    before = (tmp_path / ".env").stat()
    make_manager(tmp_path).save(SEED)
    after = (tmp_path / ".env").stat()
    assert check_secret(tmp_path / ".env") == secret
    assert after.st_mtime_ns == before.st_mtime_ns


def test_save_refuses_broken_secret(tmp_path: Path) -> None:
    write(tmp_path / ".env", b"garbage")
    with pytest.raises(SecretError):
        make_manager(tmp_path).save(SEED)
    assert (tmp_path / ".env").read_bytes() == b"garbage"
    assert not (tmp_path / "ft_otp.key").exists()


@pytest.mark.parametrize("failing", ["fsync", "replace"])
def test_save_failure_keeps_old_key_and_leaves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failing: str
) -> None:
    write(tmp_path / "ft_otp.key", b"old key")

    def boom(*args: object, **kwargs: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, failing, boom)
    with pytest.raises(WriteError):
        make_manager(tmp_path).save(SEED, replace=True)
    monkeypatch.undo()
    assert (tmp_path / "ft_otp.key").read_bytes() == b"old key"
    assert leftovers(tmp_path) == []
    assert check_secret(tmp_path / ".env") is not None  # secret created is kept


def test_save_interrupted_cleans_up_and_reraises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupt(*args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(os, "replace", interrupt)
    with pytest.raises(KeyboardInterrupt):
        make_manager(tmp_path).save(SEED)
    monkeypatch.undo()
    assert not (tmp_path / "ft_otp.key").exists()
    assert leftovers(tmp_path) == []


@pytest.mark.skipif(IS_ROOT, reason="root ignores folder permissions")
def test_save_unwritable_folder(tmp_path: Path) -> None:
    folder = tmp_path / "locked"
    folder.mkdir()
    create_secret(tmp_path / ".env")
    folder.chmod(0o500)
    try:
        with pytest.raises(WriteError):
            KeyManager(folder / "ft_otp.key", tmp_path / ".env").save(SEED)
    finally:
        folder.chmod(0o700)
    assert list(folder.iterdir()) == []


@pytest.mark.parametrize("size", [31, 513])
def test_save_rejects_seed_of_wrong_length(tmp_path: Path, size: int) -> None:
    with pytest.raises(InvalidKeyError):
        make_manager(tmp_path).save(b"\x00" * size)
    assert list(tmp_path.iterdir()) == []


def test_save_writes_no_clear_seed_to_disk(tmp_path: Path) -> None:
    key = write(tmp_path / "key.hex", HEX_64)
    manager = make_manager(tmp_path)
    manager.save(manager.prepare(key).seed)
    for path in tmp_path.iterdir():
        if path == key:
            continue
        data = path.read_bytes()
        assert SEED not in data
        assert HEX_64.encode() not in data.lower()


# ---- T6: reset (FR-17, FR-39, FR-44, FR-45) -----------------------------------


def test_reset_status_reports_each_kind(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    assert manager.reset_status() == {
        tmp_path / "ft_otp.key": PathKind.ABSENT,
        tmp_path / ".env": PathKind.ABSENT,
    }
    (tmp_path / "ft_otp.key").mkdir()
    (tmp_path / ".env").symlink_to(tmp_path / "nowhere")
    assert manager.reset_status() == {
        tmp_path / "ft_otp.key": PathKind.DIRECTORY,
        tmp_path / ".env": PathKind.OTHER,
    }


def test_reset_status_changes_nothing(tmp_path: Path) -> None:
    write(tmp_path / "ft_otp.key", b"old")
    create_secret(tmp_path / ".env")
    make_manager(tmp_path).reset_status()
    assert (tmp_path / "ft_otp.key").exists() and (tmp_path / ".env").exists()


def test_reset_erases_both_files(tmp_path: Path) -> None:
    write(tmp_path / "ft_otp.key", b"old")
    create_secret(tmp_path / ".env")
    results = make_manager(tmp_path).reset()
    assert [(r.path, r.outcome, r.error) for r in results] == [
        (tmp_path / "ft_otp.key", ResetOutcome.ERASED, None),
        (tmp_path / ".env", ResetOutcome.ERASED, None),
    ]
    assert not (tmp_path / "ft_otp.key").exists()
    assert not (tmp_path / ".env").exists()


def test_reset_reports_absent_file_and_continues(tmp_path: Path) -> None:
    create_secret(tmp_path / ".env")
    results = make_manager(tmp_path).reset()
    assert [r.outcome for r in results] == [ResetOutcome.ABSENT, ResetOutcome.ERASED]
    assert not (tmp_path / ".env").exists()


def test_reset_with_nothing_to_erase(tmp_path: Path) -> None:
    results = make_manager(tmp_path).reset()
    assert [r.outcome for r in results] == [ResetOutcome.ABSENT, ResetOutcome.ABSENT]


def test_reset_never_erases_a_directory(tmp_path: Path) -> None:
    folder = tmp_path / "ft_otp.key"
    folder.mkdir()
    write(folder / "inside.txt", b"keep me")
    create_secret(tmp_path / ".env")
    key_result, env_result = make_manager(tmp_path).reset()
    assert key_result.outcome is ResetOutcome.NOT_ERASED
    assert isinstance(key_result.error, EraseError)
    assert "manually" in str(key_result.error)
    assert (folder / "inside.txt").read_bytes() == b"keep me"
    assert env_result.outcome is ResetOutcome.ERASED
    assert not (tmp_path / ".env").exists()


def test_reset_erases_symlink_not_its_target(tmp_path: Path) -> None:
    target = write(tmp_path / "real_env", b"secret stuff")
    (tmp_path / ".env").symlink_to(target)
    _, env_result = make_manager(tmp_path).reset()
    assert env_result.outcome is ResetOutcome.ERASED
    assert not os.path.lexists(tmp_path / ".env")
    assert target.read_bytes() == b"secret stuff"


def test_reset_reports_erase_failure_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(tmp_path / "ft_otp.key", b"old")
    create_secret(tmp_path / ".env")
    real_unlink = os.unlink

    def unlink(path: object, *args: object, **kwargs: object) -> None:
        if Path(path).name == "ft_otp.key":
            raise PermissionError(13, "Permission denied")
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", unlink)
    key_result, env_result = make_manager(tmp_path).reset()
    monkeypatch.undo()
    assert key_result.outcome is ResetOutcome.NOT_ERASED
    assert isinstance(key_result.error, EraseError)
    assert "Permission denied" in str(key_result.error)
    assert (tmp_path / "ft_otp.key").exists()
    assert env_result.outcome is ResetOutcome.ERASED
