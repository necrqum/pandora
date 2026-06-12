import os
import pytest
import tempfile
from pandora.backend.security import VaultSecurity
from pandora.backend.vault import VaultManager
from pandora.backend.exceptions import DecryptionError

def test_encryption_decryption():
    sec = VaultSecurity("test_pass")
    
    plaintext = b"This is a highly secret message that should be encrypted."
    ciphertext = sec.encrypt(plaintext)
    
    assert ciphertext != plaintext
    
    decrypted = sec.decrypt(ciphertext)
    assert decrypted == plaintext

def test_wrong_password():
    sec1 = VaultSecurity("test_pass")
    sec2 = VaultSecurity("wrong_pass", salt=sec1.salt)
    
    plaintext = b"Secret"
    ciphertext = sec1.encrypt(plaintext)
    
    with pytest.raises(DecryptionError):
        sec2.decrypt(ciphertext)

def test_streaming_vault():
    sec = VaultSecurity("vault_pass")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = VaultManager(tmpdir, sec)
        
        # Test data spanning multiple chunks (if chunk size is 1MB, this is small, but still works)
        # We'll use 5 small chunks to simulate a stream
        def mock_stream():
            for i in range(5):
                yield b"Chunk " + str(i).encode() + b" data"
                
        # Store
        file_id, size = vault.store_file(mock_stream())
        assert file_id is not None
        assert os.path.exists(vault._get_file_path(file_id))
        
        # Stream back
        reconstructed = b""
        for chunk in vault.stream_file(file_id):
            reconstructed += chunk
            
        expected = b"".join(b"Chunk " + str(i).encode() + b" data" for i in range(5))
        assert reconstructed == expected

def test_db_encryption():
    # To test if sqlcipher works, we just need to try to connect to the same DB with a wrong password
    from pandora.backend.database import DatabaseManager
    import sqlite3
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        
        from sqlalchemy import text
        db1 = DatabaseManager(db_path, "good_pass")
        db1.init_db()
        session = db1.get_session()
        session.execute(text("SELECT count(*) FROM sqlite_master")).fetchall()
        session.commit()
        session.close()
        
        # Now try with raw sqlite3, should fail because it's encrypted
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("SELECT * FROM files").fetchall()
            pytest.fail("Raw sqlite3 should not be able to read the DB")
        except sqlite3.DatabaseError:
            pass # Expected
            
        # Try with wrong password using sqlcipher3
        db2 = DatabaseManager(db_path, "bad_pass")
        session2 = db2.get_session()
        with pytest.raises(Exception):
            session2.execute(text("SELECT count(*) FROM sqlite_master")).fetchall()
        session2.close()

def test_vault_range_streaming():
    from pandora.backend.security import VaultSecurity
    from pandora.backend.vault import VaultManager
    import tempfile
    
    sec = VaultSecurity("range_pass")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = VaultManager(tmpdir, sec)
        
        # Create a file with 10 small chunks to test multi-block seeking
        data_chunks = [f"Data block {i:02d} ".encode() * 100 for i in range(10)]
        def mock_stream():
            for chunk in data_chunks:
                yield chunk
        
        file_id, total_size = vault.store_file(mock_stream())
        full_data = b"".join(data_chunks)
        
        # Test full range
        reconstructed = b"".join(vault.stream_file_range(file_id, 0, total_size - 1))
        assert reconstructed == full_data
        
        # Test middle range
        start, end = 1000, 5000
        reconstructed = b"".join(vault.stream_file_range(file_id, start, end))
        assert reconstructed == full_data[start:end+1]
        
        # Test end range
        start, end = total_size - 500, total_size - 1
        reconstructed = b"".join(vault.stream_file_range(file_id, start, end))
        assert reconstructed == full_data[start:end+1]
