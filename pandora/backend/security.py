import os
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidTag

# Constants
SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32 # 256 bits for AES-256
ITERATIONS = 600_000

class VaultSecurity:
    """Handles Zero-Knowledge encryption for Pandora's Box."""

    def __init__(self, password: str, salt: bytes = None):
        """
        Initializes the security context. If a salt is provided, it derives the key
        using that salt. If not, it generates a new salt (for vault creation).
        """
        if salt is None:
            self.salt = os.urandom(SALT_SIZE)
        else:
            self.salt = salt
        
        self.key = self._derive_key(password, self.salt)
        self.aesgcm = AESGCM(self.key)

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
        """Encrypts data using AES-256-GCM. Prepend the nonce to the ciphertext."""
        nonce = os.urandom(NONCE_SIZE)
        ciphertext = self.aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext

    def decrypt(self, encrypted_data: bytes) -> bytes:
        """Decrypts data. Expects the nonce to be prepended to the ciphertext."""
        if len(encrypted_data) < NONCE_SIZE:
            raise ValueError("Encrypted data is too short")
        
        nonce = encrypted_data[:NONCE_SIZE]
        ciphertext = encrypted_data[NONCE_SIZE:]
        
        try:
            return self.aesgcm.decrypt(nonce, ciphertext, None)
        except InvalidTag:
            raise ValueError("Invalid password or corrupt data")

    def wipe(self):
        """Wipes the derived key from memory to lock the vault."""
        # Note: In Python, true memory wiping is difficult due to garbage collection,
        # but we can overwrite the reference and let GC handle it, or overwrite a bytearray.
        # Since self.key is immutable bytes, we just drop the reference and the AESGCM instance.
        self.key = None
        self.aesgcm = None
