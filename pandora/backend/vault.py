import os
import uuid
from typing import Iterator
from .security import VaultSecurity, NONCE_SIZE
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

CHUNK_SIZE = 4 * 1024 * 1024 # 4MB chunks for better streaming performance
TAG_SIZE = 16

class VaultManager:
    def __init__(self, vault_path: str, security: VaultSecurity):
        self.vault_path = vault_path
        self.security = security
        os.makedirs(self.vault_path, exist_ok=True)

    def _get_file_path(self, file_id: str) -> str:
        return os.path.join(self.vault_path, f"{file_id}.enc")

    def store_file(self, file_iterator: Iterator[bytes]) -> tuple[str, int]:
        """
        Encrypts and stores a file in fixed-size chunks.
        Guarantees that every chunk (except the last one) is exactly CHUNK_SIZE.
        Returns a tuple of (file_id, unencrypted_total_size).
        """
        file_id = str(uuid.uuid4())
        path = self._get_file_path(file_id)
        
        total_size = 0
        
        # Internal buffer to ensure fixed-size chunks reach the encryption layer
        def fixed_chunk_iterator():
            buffer = bytearray()
            for chunk in file_iterator:
                buffer.extend(chunk)
                while len(buffer) >= CHUNK_SIZE:
                    yield bytes(buffer[:CHUNK_SIZE])
                    del buffer[:CHUNK_SIZE]
            if buffer:
                yield bytes(buffer)

        with open(path, 'wb') as f:
            for chunk in fixed_chunk_iterator():
                total_size += len(chunk)
                nonce = os.urandom(NONCE_SIZE)
                ciphertext = self.security.aesgcm.encrypt(nonce, chunk, None)
                
                # Each block: [4 bytes block_size][nonce][ciphertext]
                block = nonce + ciphertext
                block_size = len(block)
                f.write(block_size.to_bytes(4, byteorder='big'))
                f.write(block)
                
        return file_id, total_size

    def stream_file(self, file_id: str) -> Iterator[bytes]:
        """Reads and decrypts a file in chunks, yielding plaintext."""
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
                
                nonce = block[:NONCE_SIZE]
                ciphertext = block[NONCE_SIZE:]
                yield self.security.aesgcm.decrypt(nonce, ciphertext, None)

    def stream_file_range(self, file_id: str, start: int, end: int) -> Iterator[bytes]:
        """
        Reads and decrypts specific byte ranges.
        Optimized to seek directly to the necessary chunks by detecting the file's chunk size.
        """
        path = self._get_file_path(file_id)
        if not os.path.exists(path):
            raise FileNotFoundError("File not found in vault")

        with open(path, 'rb') as f:
            # Read first block size to detect the nominal chunk size used when this file was stored.
            # This ensures backward compatibility with older files using different chunk sizes (e.g. 1MB vs 4MB).
            size_header = f.read(4)
            if not size_header:
                return
            
            first_block_size = int.from_bytes(size_header, byteorder='big')
            # Nominal chunk size = block_size - nonce (12) - tag (16)
            detected_nominal_chunk_size = max(1, first_block_size - (NONCE_SIZE + TAG_SIZE))
            # Every block on disk has a 4-byte size header
            full_block_on_disk = first_block_size + 4
            
            start_chunk_idx = start // detected_nominal_chunk_size
            f.seek(start_chunk_idx * full_block_on_disk)
            
            current_byte = start_chunk_idx * detected_nominal_chunk_size
            
            while current_byte <= end:
                size_bytes = f.read(4)
                if not size_bytes:
                    break
                
                block_size = int.from_bytes(size_bytes, byteorder='big')
                block = f.read(block_size)
                
                if len(block) != block_size:
                    break
                    
                nonce = block[:NONCE_SIZE]
                ciphertext = block[NONCE_SIZE:]
                plaintext = self.security.aesgcm.decrypt(nonce, ciphertext, None)
                
                chunk_start = current_byte
                slice_start = max(0, start - chunk_start)
                slice_end = min(len(plaintext), end - chunk_start + 1)
                
                if slice_start < slice_end:
                    yield plaintext[slice_start:slice_end]
                
                current_byte += len(plaintext)
                if current_byte > end:
                    break

    def delete_file(self, file_id: str):
        """Deletes an encrypted file from the vault."""
        path = self._get_file_path(file_id)
        if os.path.exists(path):
            os.remove(path)
