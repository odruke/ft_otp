"""Tests for the secret file helpers (spec 001, task T3)."""

import os
import stat
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from ft_otp.errors import KeyManagerError, SecretError
from ft_otp.secret import ENV_VAR, check_secret, create_secret

IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0


def write_env(path: Path, content: bytes | str, mode: int = 0o600) -> Path:
    if isinstance(content, str):
        content = content.encode()
    path.write_bytes(content)
    path.chmod(mode)
    return path


def valid_env(path: Path, mode: int = 0o600) -> bytes:
    secret = Fernet.generate_key()
    write_env(path, f"{ENV_VAR}={secret.decode()}\n", mode)
    return secret


# ---- check_secret (FR-18, FR-19, FR-46, FR-47) -------------------------------


def test_check_secret_absent_returns_none(tmp_path: Path) -> None:
    assert check_secret(tmp_path / ".env") is None


def test_check_secret_valid_returns_secret(tmp_path: Path) -> None:
    secret = valid_env(tmp_path / ".env")
    assert check_secret(tmp_path / ".env") == secret


def test_check_secret_rejects_directory(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.mkdir()
    with pytest.raises(SecretError, match="regular"):
        check_secret(env)


def test_check_secret_rejects_symlink_before_permissions(tmp_path: Path) -> None:
    target = tmp_path / "real_env"
    valid_env(target, mode=0o644)  # loose permissions too: regular-file check wins
    env = tmp_path / ".env"
    env.symlink_to(target)
    with pytest.raises(SecretError, match="regular"):
        check_secret(env)


def test_check_secret_rejects_loose_permissions(tmp_path: Path) -> None:
    valid_env(tmp_path / ".env", mode=0o644)
    with pytest.raises(SecretError, match="chmod 600"):
        check_secret(tmp_path / ".env")


@pytest.mark.parametrize(
    "content",
    [
        b"",
        f"{ENV_VAR}=not-a-fernet-key\n".encode(),
        b"OTHER_VAR=abc\n",
        b"\xff\xfe\xfd",
    ],
    ids=["empty", "garbage-value", "missing-variable", "invalid-utf8"],
)
def test_check_secret_rejects_unusable_content(tmp_path: Path, content: bytes) -> None:
    write_env(tmp_path / ".env", content)
    with pytest.raises(SecretError, match="reset"):
        check_secret(tmp_path / ".env")


def test_check_secret_messages_never_contain_the_secret(tmp_path: Path) -> None:
    secret = valid_env(tmp_path / ".env", mode=0o640)
    with pytest.raises(SecretError) as excinfo:
        check_secret(tmp_path / ".env")
    assert secret.decode() not in str(excinfo.value)


# ---- create_secret (FR-16, FR-17, FR-34) ---------------------------------------


def test_create_secret_makes_owner_only_file_with_valid_key(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    secret = create_secret(env)
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    Fernet(secret)  # valid Fernet key
    assert check_secret(env) == secret


def test_create_secret_never_overwrites(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    original = valid_env(env)
    with pytest.raises(SecretError):
        create_secret(env)
    assert check_secret(env) == original


@pytest.mark.skipif(IS_ROOT, reason="root ignores folder permissions")
def test_create_secret_unwritable_folder(tmp_path: Path) -> None:
    folder = tmp_path / "locked"
    folder.mkdir(mode=0o500)
    try:
        with pytest.raises(SecretError):
            create_secret(folder / ".env")
    finally:
        folder.chmod(0o700)


def test_secret_error_is_a_key_manager_error() -> None:
    assert issubclass(SecretError, KeyManagerError)
