"""
Pandora Custom Exception Hierarchy.

Provides granular, catchable error types for every subsystem so that
callers can distinguish between e.g. a wrong password and a corrupt
database — instead of catching bare ``Exception``.

Usage example::

    from pandora.backend.exceptions import InvalidPasswordError

    try:
        vault.unlock(password)
    except InvalidPasswordError:
        # user gave bad password — prompt again
    except VaultCorruptionError:
        # data integrity issue — alert user
"""


# ── Base ─────────────────────────────────────────────────────────────
class PandoraError(Exception):
    """Root exception for all Pandora errors."""


# ── Vault ────────────────────────────────────────────────────────────
class VaultError(PandoraError):
    """Base for vault-related errors."""


class VaultLockedError(VaultError):
    """Raised when an operation requires an unlocked vault."""


class VaultCorruptionError(VaultError):
    """Raised when vault data fails integrity checks (block size mismatch, etc.)."""


class VaultStorageError(VaultError):
    """Raised on disk I/O failures during vault operations."""


class FileNotFoundInVaultError(VaultError):
    """Raised when a requested file ID does not exist in the vault."""


class RangeNotSatisfiableError(VaultError):
    """Raised when a byte-range request cannot be fulfilled."""


# ── Security ─────────────────────────────────────────────────────────
class SecurityError(PandoraError):
    """Base for security / cryptography errors."""


class InvalidPasswordError(SecurityError):
    """Raised when the provided password is incorrect."""


class WeakPasswordError(SecurityError):
    """Raised when the provided password does not meet minimum requirements."""


class EncryptionError(SecurityError):
    """Raised when encryption of data fails."""


class DecryptionError(SecurityError):
    """Raised when decryption of data fails (wrong key, corrupt ciphertext)."""


# ── Database ─────────────────────────────────────────────────────────
class DatabaseError(PandoraError):
    """Base for database errors."""


class DatabaseConnectionError(DatabaseError):
    """Raised when the database cannot be opened or connected to."""


class DatabaseIntegrityError(DatabaseError):
    """Raised on constraint violations or data integrity failures."""


# ── Streaming ────────────────────────────────────────────────────────
class FileStreamError(PandoraError):
    """Base for errors during file streaming to the client."""
