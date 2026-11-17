"""Exceptions raised by the core: one class per error category (NFR-2).

Messages are ready to show to the user and never contain the seed or
the secret.
"""


class KeyManagerError(Exception):
    """Base class for every error raised by the key-management core."""


class InvalidKeyError(KeyManagerError):
    """The key is not valid hexadecimal text of the allowed length."""


class KeyFileNotFoundError(KeyManagerError):
    """The key file does not exist."""


class UnsupportedFileError(KeyManagerError):
    """A file cannot be read, is too large, or is not a regular file."""


class KeyExistsError(KeyManagerError):
    """ft_otp.key already exists and replacement was not confirmed."""


class SecretError(KeyManagerError):
    """The secret file cannot be created or used."""


class WriteError(KeyManagerError):
    """The stored key file could not be written."""


class EraseError(KeyManagerError):
    """A file could not be erased during a reset."""
