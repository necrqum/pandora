import os
import logging
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidTag

from .exceptions import (
    SecurityError, InvalidPasswordError, WeakPasswordError,
    EncryptionError, DecryptionError,
)

logger = logging.getLogger("pandora.security")

MIN_PASSWORD_LENGTH = 8

# Constants
SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32 # 256 bits for AES-256
ITERATIONS = 600_000

class VaultSecurity:
    """Handles Zero-Knowledge encryption for Pandora's Box."""

    def __init__(self, password: str, salt: bytes = None, *, skip_validation: bool = False):
        """
        Initializes the security context. If a salt is provided, it derives the key
        using that salt. If not, it generates a new salt (for vault creation).

        Args:
            password: The user's master password.
            salt: Existing salt for key re-derivation.  ``None`` generates a new one.
            skip_validation: If ``True``, skips password-strength checks
                (used internally when we only need to *verify* an existing password).

        Raises:
            WeakPasswordError: If the password is too short or empty (and validation isn't skipped).
            SecurityError: If key derivation fails for unexpected reasons.
        """
        if not password:
            raise WeakPasswordError("Password must not be empty.")
        if not skip_validation and len(password) < MIN_PASSWORD_LENGTH:
            raise WeakPasswordError(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters long "
                f"(got {len(password)})."
            )

        if salt is None:
            self.salt = os.urandom(SALT_SIZE)
        else:
            self.salt = salt

        try:
            self.key = self._derive_key(password, self.salt)
            self.aesgcm = AESGCM(self.key)
        except Exception as exc:
            logger.error("Key derivation failed: %s", exc)
            raise SecurityError(f"Failed to derive encryption key: {exc}") from exc

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        """Derives a 256-bit key using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=salt,
            iterations=ITERATIONS,
        )
        return kdf.derive(password.encode('utf-8'))

    def encrypt(self, data: bytes) -> bytes:
        """Encrypts data using AES-256-GCM. Prepend the nonce to the ciphertext.

        Raises:
            EncryptionError: If the AES-GCM encryption operation fails.
        """
        if self.aesgcm is None:
            raise EncryptionError("Cannot encrypt: vault security context has been wiped.")
        try:
            nonce = os.urandom(NONCE_SIZE)
            ciphertext = self.aesgcm.encrypt(nonce, data, None)
            return nonce + ciphertext
        except Exception as exc:
            logger.error("Encryption failed: %s", exc)
            raise EncryptionError(f"AES-GCM encryption failed: {exc}") from exc

    def decrypt(self, encrypted_data: bytes) -> bytes:
        """Decrypts data. Expects the nonce to be prepended to the ciphertext.

        Raises:
            DecryptionError: If the data is too short, the password is wrong,
                or the ciphertext is corrupt.
        """
        if self.aesgcm is None:
            raise DecryptionError("Cannot decrypt: vault security context has been wiped.")
        if len(encrypted_data) < NONCE_SIZE:
            raise DecryptionError(
                f"Encrypted data too short ({len(encrypted_data)} bytes, "
                f"minimum is {NONCE_SIZE})."
            )

        nonce = encrypted_data[:NONCE_SIZE]
        ciphertext = encrypted_data[NONCE_SIZE:]

        try:
            return self.aesgcm.decrypt(nonce, ciphertext, None)
        except InvalidTag:
            raise DecryptionError("Decryption failed: invalid password or corrupt data.")
        except Exception as exc:
            logger.error("Unexpected decryption error: %s", exc)
            raise DecryptionError(f"Decryption failed: {exc}") from exc

    def wipe(self):
        """Wipes the derived key from memory to lock the vault."""
        # Note: In Python, true memory wiping is difficult due to garbage collection,
        # but we can overwrite the reference and let GC handle it, or overwrite a bytearray.
        # Since self.key is immutable bytes, we just drop the reference and the AESGCM instance.
        self.key = None
        self.aesgcm = None

def generate_self_signed_cert(cert_path: str, key_path: str):
    import os
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return
        
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    import datetime

    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"pandora-local"),
    ])
    
    # Use timezone-aware UTC datetime per cryptography library requirements
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.now(datetime.timezone.utc)
    ).not_valid_after(
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650)
    ).sign(key, hashes.SHA256())
    
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
        
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
