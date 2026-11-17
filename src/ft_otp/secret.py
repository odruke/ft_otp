"""Secret file (.env) holding the Fernet key that encrypts ft_otp.key.

UI-agnostic: returns values or raises SecretError, never prints or prompts.
Messages never contain the secret.
"""

import os
import stat
from pathlib import Path

from cryptography.fernet import Fernet

from ft_otp.errors import SecretError

ENV_VAR = "FT_OTP_SECRET"


def read_env_file(path: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE lines, ignoring blanks and comments."""
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            name, _, value = line.partition('=')
            values[name.strip()] = value.strip()
    return values


def create_secret(path: Path) -> bytes:
    """Create .env with a new random key. Fails if the file already exists."""
    secret = Fernet.generate_key()
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(f"{ENV_VAR}={secret.decode()}\n")
    except OSError as e:
        raise SecretError(
            f"{path}: cannot create the secret file: {e.strerror}."
        ) from None
    return secret


def check_secret(path: Path) -> bytes | None:
    """Return the secret in .env, or None if .env does not exist.

    Checks, in this order: regular file, owner-only permissions, usable key.
    """
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise SecretError(
            f"{path}: the secret file is not a regular file. "
            "Remove it, or run ft_otp --reset "
            "(if it is a directory, you must remove it manually)."
        )
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise SecretError(
            f"{path}: the secret file can be accessed by other users, who "
            "could decrypt your stored keys. Run chmod 600 on it, or run "
            "ft_otp --reset."
        )
    try:
        value = read_env_file(path).get(ENV_VAR)
        Fernet(value)
    except (OSError, UnicodeDecodeError, ValueError, TypeError):
        raise SecretError(
            f"{path}: the secret file does not contain a usable secret, so "
            "no key can be stored or read with it. Run ft_otp --reset."
        ) from None
    return value.encode()
