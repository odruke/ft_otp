"""Key storage core (spec 001): validate, store and reset the encrypted key.

UI-agnostic: never prints, prompts, exits or logs user messages. It returns
values or raises the exceptions in ft_otp.errors.
"""

import os
import stat
import string
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from cryptography.fernet import Fernet

from ft_otp import secret
from ft_otp.errors import (
    EraseError,
    InvalidKeyError,
    KeyExistsError,
    KeyFileNotFoundError,
    UnsupportedFileError,
    WriteError,
)

MIN_HEX_LEN = 64
MAX_HEX_LEN = 1024
MAX_FILE_BYTES = MAX_HEX_LEN + 1  # 1024 hex digits plus one line break
KEY_FILE_NAME = "ft_otp.key"


@dataclass(frozen=True)
class PreparedKey:
    """A validated seed, ready to be saved. repr never shows the seed."""

    seed: bytes = field(repr=False)
    stored_key_exists: bool


class PathKind(Enum):
    """What a reset finds at a path."""

    ABSENT = "absent"
    DIRECTORY = "directory"
    OTHER = "other"  # regular file, symbolic link or special file: erasable


class ResetOutcome(Enum):
    """What a reset did with one file."""

    ERASED = "erased"
    ABSENT = "absent"
    NOT_ERASED = "not erased"


@dataclass(frozen=True)
class ResetResult:
    """Outcome of the reset for one file; error is set when NOT_ERASED."""

    path: Path
    outcome: ResetOutcome
    error: EraseError | None = None


class KeyManager:
    """Validate a hexadecimal key and manage its encrypted storage.

    key_path is the stored key file (ft_otp.key); secret_path is the secret
    file (.env). Both are passed in so tests can use temporary folders.
    """

    def __init__(self, key_path: Path, secret_path: Path) -> None:
        self.key_path = Path(key_path)
        self.secret_path = Path(secret_path)

    @staticmethod
    def parse_hex(text: str) -> bytes:
        """Return the seed bytes of a hex key, ignoring surrounding whitespace.

        Rules are checked in this order, and only the first broken one is
        reported: hexadecimal characters, even count, length range.
        """
        text = text.strip()
        if any(c not in string.hexdigits for c in text):
            raise InvalidKeyError(
                "The key must contain only hexadecimal characters."
            )
        if len(text) % 2 != 0:
            raise InvalidKeyError(
                "The key must have an even number of characters."
            )
        if not MIN_HEX_LEN <= len(text) <= MAX_HEX_LEN:
            raise InvalidKeyError(
                f"The key must have between {MIN_HEX_LEN} and {MAX_HEX_LEN} "
                "hexadecimal characters."
            )
        return bytes.fromhex(text)

    @staticmethod
    def read_key_file(path: Path) -> bytes:
        """Read a key file and return its seed bytes.

        File checks come first, in this order: exists, regular file (symbolic
        links are never followed), at most MAX_FILE_BYTES, readable UTF-8.
        Then the content is validated by parse_hex. The file is only read.
        """
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            raise KeyFileNotFoundError(f"{path}: file not found.") from None
        if not stat.S_ISREG(info.st_mode):
            raise UnsupportedFileError(f"{path}: not a regular file.")
        if info.st_size > MAX_FILE_BYTES:
            raise UnsupportedFileError(
                f"{path}: too large to contain a valid key."
            )
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                data = os.read(fd, MAX_FILE_BYTES + 1)
            finally:
                os.close(fd)
        except OSError:
            raise UnsupportedFileError(
                f"{path}: cannot read a hexadecimal key from it."
            ) from None
        if len(data) > MAX_FILE_BYTES:  # the file grew after the size check
            raise UnsupportedFileError(
                f"{path}: too large to contain a valid key."
            )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise UnsupportedFileError(
                f"{path}: cannot read a hexadecimal key from it."
            ) from None
        return KeyManager.parse_hex(text)

    def check_secret(self) -> None:
        """Raise SecretError if an existing secret file cannot be used."""
        secret.check_secret(self.secret_path)

    def stored_key_exists(self) -> bool:
        """True if the stored key file exists. Its content is never read."""
        try:
            info = os.lstat(self.key_path)
        except FileNotFoundError:
            return False
        if not stat.S_ISREG(info.st_mode):
            raise UnsupportedFileError(
                f"{self.key_path}: not a regular file. Remove it, or run "
                "ft_otp --reset (if it is a directory, you must remove it "
                "manually)."
            )
        return True

    def prepare(self, key_file: Path) -> PreparedKey:
        """Run every check before a store, in order, without creating anything.

        Key file first, then the secret file, then the stored key file, so the
        caller can ask about replacement only when the store can succeed.
        """
        seed = self.read_key_file(key_file)
        self.check_secret()
        return PreparedKey(seed, self.stored_key_exists())

    def save(self, seed: bytes, replace: bool = False) -> None:
        """Encrypt the seed and write it to the stored key file.

        An existing stored key file is replaced only if replace is True. The
        secret file is created here, the first time a key is written.
        """
        if not MIN_HEX_LEN // 2 <= len(seed) <= MAX_HEX_LEN // 2:
            raise InvalidKeyError(
                f"The key must have between {MIN_HEX_LEN} and {MAX_HEX_LEN} "
                "hexadecimal characters."
            )
        if self.stored_key_exists() and not replace:
            raise KeyExistsError(
                f"{self.key_path}: a stored key already exists."
            )
        key = secret.check_secret(self.secret_path)
        if key is None:
            key = secret.create_secret(self.secret_path)
        self._write_atomic(Fernet(key).encrypt(seed))

    def _write_atomic(self, data: bytes) -> None:
        """Write a temporary file (mode 0600) next to key_path, then swap it.

        At any moment key_path holds the complete old or the complete new
        content; on any failure the temporary file is removed.
        """
        tmp = None
        try:
            fd, tmp = tempfile.mkstemp(
                dir=self.key_path.parent, prefix=f".{self.key_path.name}."
            )
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.key_path)
        except BaseException as e:
            if tmp is not None and os.path.lexists(tmp):
                os.unlink(tmp)
            if isinstance(e, OSError):
                raise WriteError(
                    f"{self.key_path}: cannot write the stored key: "
                    f"{e.strerror}."
                ) from None
            raise

    def reset_status(self) -> dict[Path, PathKind]:
        """Describe the stored key file and the secret file (read-only)."""
        status = {}
        for path in (self.key_path, self.secret_path):
            try:
                info = os.lstat(path)
            except FileNotFoundError:
                status[path] = PathKind.ABSENT
                continue
            if stat.S_ISDIR(info.st_mode):
                status[path] = PathKind.DIRECTORY
            else:
                status[path] = PathKind.OTHER
        return status

    def reset(self) -> list[ResetResult]:
        """Erase the stored key file, then the secret file.

        Each file is handled on its own, so a failure never stops the other.
        Directories are never erased; a symbolic link is erased, not its
        target.
        """
        paths = (self.key_path, self.secret_path)
        return [self._erase(path) for path in paths]

    @staticmethod
    def _erase(path: Path) -> ResetResult:
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            return ResetResult(path, ResetOutcome.ABSENT)
        if stat.S_ISDIR(info.st_mode):
            return ResetResult(
                path,
                ResetOutcome.NOT_ERASED,
                EraseError(
                    f"{path}: is a directory and was not erased; "
                    "you must fix it manually."
                ),
            )
        try:
            os.unlink(path)
        except OSError as e:
            return ResetResult(
                path,
                ResetOutcome.NOT_ERASED,
                EraseError(f"{path}: cannot be erased: {e.strerror}."),
            )
        return ResetResult(path, ResetOutcome.ERASED)
