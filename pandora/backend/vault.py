import os
import uuid
from typing import Iterator
from .security import VaultSecurity, NONCE_SIZE
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

CHUNK_SIZE = 1024 * 1024 # 1MB chunks for streaming
TAG_SIZE = 16

class VaultManager:
    def __init__(self, vault_path: str, security: VaultSecurity):
        self.vault_path = vault_path
        self.security = security
        os.makedirs(self.vault_path, exist_ok=True)

    def _get_file_path(self, file_id: str) -> str:
        return os.path.join(self.vault_path, f"{file_id}.enc")

    def store_file(self, file_iterator: Iterator[bytes]) -> str:
        """
        Encrypts and stores a file in chunks.
        Returns the unique file UUID.
        """
        file_id = str(uuid.uuid4())
        path = self._get_file_path(file_id)
        
        with open(path, 'wb') as f:
            for chunk in file_iterator:
                # Encrypt each chunk independently with a new nonce
                nonce = os.urandom(NONCE_SIZE)
                ciphertext = self.security.aesgcm.encrypt(nonce, chunk, None)
                
                # Write nonce length (12) + ciphertext length + tag length (16)
                # We can just write nonce + ciphertext because the chunk size varies only on the last chunk,
                # but we need a way to read it back. We'll write the size of the ciphertext block.
                # Actually, standard chunk size makes reading easy: NONCE + CIPHERTEXT
                # For a 1MB plaintext, the ciphertext is 1MB + 16 bytes.
                block = nonce + ciphertext
                block_size = len(block)
                f.write(block_size.to_bytes(4, byteorder='big'))
                f.write(block)
                
        return file_id

    def stream_file(self, file_id: str) -> Iterator[bytes]:
        """
        Reads and decrypts a file in chunks, yielding plaintext.
        This provides in-memory streaming directly to the client.
        """
        path = self._get_file_path(file_id)
        if not os.path.exists(path):
            raise FileNotFoundError("File not found in vault")
            
        with open(path, 'rb') as f:
            while True:
                size_bytes = f.read(4)
                if not size_bytes:
                    break
                
                block_size = int.from_bytes(size_bytes, byteorder='big')
                block = f.read(block_size)
                
                if len(block) != block_size:
                    raise ValueError("Corrupt file: block size mismatch")
                    
                nonce = block[:NONCE_SIZE]
                ciphertext = block[NONCE_SIZE:]
                
                plaintext = self.security.aesgcm.decrypt(nonce, ciphertext, None)
                yield plaintext

    def delete_file(self, file_id: str):
        """Deletes an encrypted file from the vault."""
        path = self._get_file_path(file_id)
        if os.path.exists(path):
            os.remove(path)
