from fastapi import FastAPI, HTTPException, UploadFile, Depends, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import os

from .security import VaultSecurity
from .database import DatabaseManager, File as DBFile
from .vault import VaultManager, CHUNK_SIZE

app = FastAPI(title="Pandora Web Vault")

# Serve frontend files
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
os.makedirs(frontend_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
def serve_index():
    with open(os.path.join(frontend_dir, "index.html"), "r") as f:
        return HTMLResponse(content=f.read())

# Global state for the unlocked vault session
# In a true multi-user production app, this would be tied to session cookies.
# Since this is a single-user self-hosted app, we can store it in memory.
class AppState:
    security: Optional[VaultSecurity] = None
    db: Optional[DatabaseManager] = None
    vault: Optional[VaultManager] = None
    vault_dir: str = os.path.expanduser("~/.pandora")

state = AppState()

# Ensure vault directory exists
os.makedirs(state.vault_dir, exist_ok=True)
salt_path = os.path.join(state.vault_dir, ".vault_salt")
db_path = os.path.join(state.vault_dir, "pandora.db")
files_path = os.path.join(state.vault_dir, "files")

# --- Models ---
class InitRequest(BaseModel):
    password: str

class UnlockRequest(BaseModel):
    password: str

class FileResponse(BaseModel):
    id: str
    filename: str

# --- Dependency ---
def require_unlocked():
    if not state.security or not state.db or not state.vault:
        raise HTTPException(status_code=401, detail="Vault is locked")

# --- Routes ---
@app.post("/api/init")
def init_vault(req: InitRequest):
    if os.path.exists(salt_path):
        raise HTTPException(status_code=400, detail="Vault already initialized")
    
    state.security = VaultSecurity(req.password)
    with open(salt_path, 'wb') as f:
        f.write(state.security.salt)
        
    state.db = DatabaseManager(db_path, req.password)
    state.db.init_db()
    
    state.vault = VaultManager(files_path, state.security)
    return {"status": "ok"}

@app.post("/api/unlock")
def unlock_vault(req: UnlockRequest):
    if not os.path.exists(salt_path):
        raise HTTPException(status_code=400, detail="Vault not initialized")
        
    with open(salt_path, 'rb') as f:
        salt = f.read()
        
    try:
        # Test password by deriving key and attempting to open DB
        security = VaultSecurity(req.password, salt)
        db = DatabaseManager(db_path, req.password)
        
        # Test DB connection to ensure password is correct by reading from disk
        from sqlalchemy import text
        session = db.get_session()
        session.execute(text("SELECT count(*) FROM sqlite_master")).fetchall()
        session.close()
        
        state.security = security
        state.db = db
        state.vault = VaultManager(files_path, security)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid password")

@app.post("/api/lock")
def lock_vault():
    if state.security:
        state.security.wipe()
    state.security = None
    state.db = None
    state.vault = None
    return {"status": "locked"}

@app.post("/api/files", dependencies=[Depends(require_unlocked)])
def upload_file(file: UploadFile):
    def file_iterator():
        while True:
            chunk = file.file.read(CHUNK_SIZE)
            if not chunk:
                break
            yield chunk

    # Store encrypted file
    file_id = state.vault.store_file(file_iterator())
    
    # Save metadata to DB
    session = state.db.get_session()
    db_file = DBFile(id=file_id, filename=file.filename)
    session.add(db_file)
    session.commit()
    session.close()
    
    return {"id": file_id, "filename": file.filename}

@app.get("/api/files", response_model=List[FileResponse], dependencies=[Depends(require_unlocked)])
def list_files():
    session = state.db.get_session()
    files = session.query(DBFile).all()
    res = [{"id": f.id, "filename": f.filename} for f in files]
    session.close()
    return res

@app.get("/api/files/{file_id}", dependencies=[Depends(require_unlocked)])
def stream_file(file_id: str):
    # Check if file exists in DB
    session = state.db.get_session()
    db_file = session.query(DBFile).filter(DBFile.id == file_id).first()
    session.close()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        iterator = state.vault.stream_file(file_id)
        # Assuming MP4 for simplicity, a real app would infer from filename/metadata
        return StreamingResponse(iterator, media_type="video/mp4")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def start():
    import uvicorn
    uvicorn.run("pandora.backend.main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    start()
