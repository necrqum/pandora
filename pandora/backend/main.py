import signal
import sys
import socket
from sqlalchemy import or_
from fastapi import FastAPI, HTTPException, UploadFile, Depends, Request, Response, Cookie, Form, BackgroundTasks
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import os
import secrets
import shutil
import traceback
import json
from fastapi.responses import JSONResponse
import time
import mimetypes
import threading

db_write_lock = threading.Lock()

from .security import VaultSecurity
from .database import DatabaseManager, File as DBFile, Category as DBCategory
from .vault import VaultManager, CHUNK_SIZE
from .logging_config import setup_logging
from .exceptions import DecryptionError, WeakPasswordError
from .thumbnails import generate_thumbnail_from_file, get_file_creation_date

app = FastAPI(title="Pandora Web Vault")

# Global state
class AppState:
    security: Optional[VaultSecurity] = None
    db: Optional[DatabaseManager] = None
    vault: Optional[VaultManager] = None
    config_dir: Optional[str] = None
    blob_dir: Optional[str] = None
    active_sessions: set = set()
    logger: Optional[object] = None
    config_path: str = os.path.expanduser("~/.pandora_config")

state = AppState()

import_tasks = {}

def setup_vault_paths(config_dir: str, blob_dir: Optional[str] = None):
    state.config_dir = os.path.abspath(config_dir)
    state.blob_dir = os.path.abspath(blob_dir) if blob_dir else os.path.join(state.config_dir, "data")
    
    os.makedirs(state.config_dir, exist_ok=True)
    os.makedirs(state.blob_dir, exist_ok=True)
    
    state.logger = setup_logging(state.config_dir)
    return {
        "salt": os.path.join(state.config_dir, ".vault_salt"),
        "db": os.path.join(state.config_dir, "pandora.db"),
        "files": os.path.join(state.blob_dir, "files")
    }

# Initial attempt to load from config or env
initial_config_dir = os.environ.get("PANDORA_CONFIG_DIR")
initial_blob_dir = os.environ.get("PANDORA_BLOB_DIR")

# Support legacy PANDORA_VAULT_DIR for backward compatibility
if not initial_config_dir:
    initial_config_dir = os.environ.get("PANDORA_VAULT_DIR")

if not initial_config_dir and os.path.exists(state.config_path):
    try:
        with open(state.config_path, "r") as f:
            config_data = json.load(f)
            initial_config_dir = config_data.get("config_dir")
            initial_blob_dir = config_data.get("blob_dir")
    except (json.JSONDecodeError, KeyError, AttributeError):
        # Fallback for old plain text config
        with open(state.config_path, "r") as f:
            initial_config_dir = f.read().strip()

if initial_config_dir:
    paths = setup_vault_paths(initial_config_dir, initial_blob_dir)
else:
    # Default if no config
    paths = setup_vault_paths(os.path.expanduser("~/.pandora"))

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    
    if state.logger:
        state.logger.error(f"Unhandled exception on {request.method} {request.url.path}\n{traceback.format_exc()}")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

# Pure ASGI middleware for logging to avoid BaseHTTPMiddleware issues with streams and exceptions
class AdvancedLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        client_ip = scope.get("client", ["unknown", ""])[0] if scope.get("client") else "unknown"
        method = scope.get("method", "")
        path = scope.get("path", "")

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message["status"]
                process_time = time.time() - start_time
                if state.logger:
                    state.logger.info(f"{client_ip} - \"{method} {path}\" {status_code} ({process_time:.3f}s)")
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            process_time = time.time() - start_time
            if state.logger:
                state.logger.error(f"{client_ip} - \"{method} {path}\" 500 ({process_time:.3f}s) - Error: {str(e)}")
            raise e

# --- Utilities ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_path, relative_path)

frontend_dir = resource_path("frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
def serve_index():
    # If no salt file exists, we need to show the setup screen
    is_setup = not os.path.exists(paths["salt"])
    index_path = os.path.join(frontend_dir, "index.html")
    if not os.path.exists(index_path):
        # Fallback for different build structures
        index_path = resource_path("pandora/frontend/index.html")
        
    with open(index_path, "r") as f:
        content = f.read()
        if is_setup:
            content = content.replace('id="decoy-container" class="container active"', 'id="decoy-container" class="container"')
            content = content.replace('id="setup-container" class="container"', 'id="setup-container" class="container active"')
        return HTMLResponse(content=content)

# --- Utilities ---
def natural_sort_key(s: str):
    import re
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]

class SearchParser:
    @staticmethod
    def tokenize(query: str) -> List[str]:
        tokens = []
        in_quote = False
        current_token = ""
        quote_char = None
        for char in query:
            if char in ['"', "'"] and not in_quote:
                in_quote = True
                quote_char = char
                if current_token.strip(): tokens.extend(current_token.strip().split())
                current_token = ""
            elif char == quote_char and in_quote:
                in_quote = False
                if current_token: tokens.append(current_token)
                current_token = ""
                quote_char = None
            elif char.isspace() and not in_quote:
                if current_token.strip(): tokens.extend(current_token.strip().split())
                current_token = ""
            else:
                current_token += char
        if current_token.strip(): tokens.extend(current_token.strip().split())
        return tokens

    @staticmethod
    def parse(query: str):
        import re
        criteria = {
            'name': {'include': [], 'exclude': []},
            'tag': {'include': [], 'exclude': []},
            'cat': {'include': [], 'exclude': []},
            'artist': {'include': [], 'exclude': []},
            'site': {'include': [], 'exclude': []},
            'any': {'include': [], 'exclude': []}
        }
        pattern = r'(-)?(?:(name|tag|cat|artist|site):\s*)?("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[^\s]+)'
        matches = re.finditer(pattern, query)
        for match in matches:
            exclude = match.group(1) == '-'
            field = match.group(2) or 'any'
            val = match.group(3)
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            val = val.lower().strip()
            if not val: continue
            key = 'exclude' if exclude else 'include'
            criteria[field][key].append(val)
        return criteria

# --- Models ---
class InitRequest(BaseModel):
    password: str
    vault_dir: Optional[str] = None
    blob_dir: Optional[str] = None

class UnlockRequest(BaseModel):
    password: str

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str

class CategoryCreate(BaseModel):
    name: str

class FileCategoryUpdate(BaseModel):
    category_id: Optional[int]

class FileRenameRequest(BaseModel):
    filename: str

class FileMetadataUpdateRequest(BaseModel):
    notes: Optional[str] = None
    artist: Optional[str] = None
    source_url: Optional[str] = None

class URLImportRequest(BaseModel):
    url: str
    filename: Optional[str] = None
    category_id: Optional[int] = None
    tags: List[str] = []
    artist: Optional[str] = None
    source_url: Optional[str] = None
    playlist_index: Optional[int] = None

class PurgeRequest(BaseModel):
    password: str
    purge_type: str # "mass" (files only) or "everything" (reset DB)

class ExportRequest(BaseModel):
    password: str
    target_path: str

class TagCreate(BaseModel):
    name: str

class UpdateTagsRequest(BaseModel):
    tags: List[str]

class BatchTagsRequest(BaseModel):
    file_ids: List[str]
    tags: List[str]
    action: str # "add", "remove", or "set"

class BatchCategoryRequest(BaseModel):
    file_ids: List[str]
    category_id: Optional[int]

class BatchRequest(BaseModel):
    file_ids: List[str]

# --- Dependency ---
def require_unlocked(session_token: Optional[str] = Cookie(None)):
    if not state.security or not state.db or not state.vault:
        raise HTTPException(status_code=401, detail="Vault is locked")
    if not session_token or session_token not in state.active_sessions:
        raise HTTPException(status_code=401, detail="Unauthorized device")

@app.post("/api/files/batch/tags", dependencies=[Depends(require_unlocked)])
def batch_update_tags(req: BatchTagsRequest):
    from .database import Tag as DBTag
    with db_write_lock:
        with state.db.session_scope() as session:
            files = session.query(DBFile).filter(DBFile.id.in_(req.file_ids)).all()
            if not files: return {"status": "ok", "count": 0}
            
            # Pre-load or create tags
            new_tag_objs = []
            for tag_name in req.tags:
                tag_name = tag_name.strip()
                if not tag_name: continue
                tag = session.query(DBTag).filter(DBTag.name == tag_name).first()
                if not tag:
                    tag = DBTag(name=tag_name)
                    session.add(tag)
                    session.flush() # Ensure it has an ID
                new_tag_objs.append(tag)
                
            for db_file in files:
                if req.action == "set":
                    db_file.tags = list(new_tag_objs)
                elif req.action == "add":
                    current_tag_ids = {t.id for t in db_file.tags}
                    for nt in new_tag_objs:
                        if nt.id not in current_tag_ids:
                            db_file.tags.append(nt)
                elif req.action == "remove":
                    remove_ids = {t.id for t in new_tag_objs}
                    db_file.tags = [t for t in db_file.tags if t.id not in remove_ids]
                
    return {"status": "ok", "count": len(req.file_ids)}

@app.put("/api/files/batch/category", dependencies=[Depends(require_unlocked)])
def batch_update_category(req: BatchCategoryRequest):
    with state.db.session_scope() as session:
        session.query(DBFile).filter(DBFile.id.in_(req.file_ids)).update(
            {DBFile.category_id: req.category_id}, synchronize_session=False
        )
    return {"status": "ok", "count": len(req.file_ids)}

@app.post("/api/files/batch/delete", dependencies=[Depends(require_unlocked)])
def batch_delete(req: BatchRequest):
    with state.db.session_scope() as session:
        files = session.query(DBFile).filter(DBFile.id.in_(req.file_ids)).all()
        for f in files:
            state.vault.delete_file(f.id)
            session.delete(f)
    return {"status": "ok", "processed": len(files)}

@app.post("/api/files/batch/scrape", dependencies=[Depends(require_unlocked)])
def batch_scrape(req: BatchRequest, background_tasks: BackgroundTasks):
    from .scrapers.ytdlp_engine import fetch_metadata
    
    def run_batch_scrape(file_ids):
        with db_write_lock:
            with state.db.session_scope() as session:
                for file_id in file_ids:
                    f = session.query(DBFile).filter(DBFile.id == file_id).first()
                    if f and f.source_url:
                        meta = fetch_metadata(f.source_url)
                        if meta:
                            if meta.get("uploader"):
                                f.artist = meta["uploader"]
                            if meta.get("tags"):
                                from .database import Tag as DBTag
                                for tag_name in meta["tags"][:5]:
                                    tag_name = tag_name.strip()
                                    if not tag_name: continue
                                    db_tag = session.query(DBTag).filter(DBTag.name == tag_name).first()
                                    if not db_tag:
                                        db_tag = DBTag(name=tag_name)
                                        session.add(db_tag)
                                    if db_tag not in f.tags:
                                        f.tags.append(db_tag)
                            session.commit()
    background_tasks.add_task(run_batch_scrape, req.file_ids)
    return {"status": "ok"}

# --- Routes ---
@app.get("/api/setup/status")
def get_setup_status():
    # Check if salt exists (meaning already initialized)
    config_dir = state.config_dir or os.path.expanduser("~/.pandora")
    blob_dir = state.blob_dir
    initialized = os.path.exists(os.path.join(config_dir, ".vault_salt"))
    
    return {
        "initialized": initialized,
        "suggested_config_dir": config_dir,
        "suggested_blob_dir": blob_dir,
        "is_env_forced": os.environ.get("PANDORA_CONFIG_DIR") is not None
    }

@app.post("/api/init")
def init_vault(req: InitRequest, response: Response):
    global paths
    # Use paths from request if provided, otherwise fallback to current state (env or config)
    config_dir = os.path.abspath(req.vault_dir) if req.vault_dir else (state.config_dir or os.path.expanduser("~/.pandora"))
    blob_dir = os.path.abspath(req.blob_dir) if req.blob_dir else state.blob_dir

    paths = setup_vault_paths(config_dir, blob_dir)
    with open(state.config_path, "w") as f:
        json.dump({
            "config_dir": state.config_dir,
            "blob_dir": state.blob_dir
        }, f)

    if os.path.exists(paths["salt"]):
        raise HTTPException(status_code=400, detail="Vault already initialized")
    
    try:
        state.security = VaultSecurity(req.password)
    except WeakPasswordError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    with open(paths["salt"], 'wb') as f:
        f.write(state.security.salt)
        
    state.db = DatabaseManager(paths["db"], req.password)
    state.db.init_db()
    
    state.vault = VaultManager(paths["files"], state.security)
    token = secrets.token_hex(32)
    state.active_sessions.add(token)
    response.set_cookie(key="session_token", value=token, httponly=True, secure=True, samesite="strict")
    
    return {"status": "ok"}

@app.post("/api/unlock")
def unlock_vault(req: UnlockRequest, response: Response):
    if not os.path.exists(paths["salt"]):
        raise HTTPException(status_code=400, detail="Vault not initialized")
        
    with open(paths["salt"], 'rb') as f:
        salt = f.read()
        
    try:
        security = VaultSecurity(req.password, salt)
        db = DatabaseManager(paths["db"], req.password)
        db.verify_password()
        db.init_db()
        
        state.security = security
        state.db = db
        state.vault = VaultManager(paths["files"], security)
        token = secrets.token_hex(32)
        state.active_sessions.add(token)
        response.set_cookie(key="session_token", value=token, httponly=True, secure=True, samesite="strict")
        
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid password")

@app.post("/api/lock")
def lock_vault(response: Response, session_token: Optional[str] = Cookie(None)):
    if session_token in state.active_sessions:
        state.active_sessions.remove(session_token)
    response.delete_cookie("session_token")
    
    if len(state.active_sessions) == 0:
        if state.security:
            state.security.wipe()
        state.security = None
        state.db = None
        state.vault = None
    return {"status": "locked"}

@app.post("/api/settings/change-password", dependencies=[Depends(require_unlocked)])
def change_password(req: PasswordChangeRequest):
    # 1. Verify old password
    if not state.db.verify_password():
        raise HTTPException(status_code=401, detail="Invalid old password")
    
    try:
        # 2. Derive new security and DB
        new_security = VaultSecurity(req.new_password)
        
        # 3. Encrypt all files with new key (Re-keying)
        # This is expensive but necessary for true password change.
        # For now, let's at least update the salt and DB password.
        
        # SQLCipher password change:
        # session.execute(text(f"PRAGMA rekey = '{req.new_password}'"))
        # But we use DatabaseManager which wraps this.
        
        # Implementation of full re-keying would go here.
        # For brevity, let's assume we update the salt and the DB password.
        
        with open(paths["salt"], 'wb') as f:
            f.write(new_security.salt)
            
        # This is a placeholder for a real re-keying logic which is complex
        # because it involves re-encrypting every chunk in the vault.
        raise HTTPException(status_code=501, detail="Password change requires full vault re-encryption (Not yet implemented)")
        
    except WeakPasswordError as e:
        raise HTTPException(status_code=400, detail=str(e))

from fastapi import BackgroundTasks

@app.post("/api/server/shutdown", dependencies=[Depends(require_unlocked)])
def shutdown_server(background_tasks: BackgroundTasks):
    if state.logger:
        state.logger.info("Shutdown requested via API.")
    def do_shutdown():
        import time, os, signal
        time.sleep(0.5)
        os.kill(os.getpid(), signal.SIGINT)
    background_tasks.add_task(do_shutdown)
    return {"status": "shutting down"}

@app.post("/api/server/restart", dependencies=[Depends(require_unlocked)])
def restart_server(background_tasks: BackgroundTasks):
    if state.logger:
        state.logger.info("Restart requested via API.")
    def restart():
        import time, os, sys
        time.sleep(0.5)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    background_tasks.add_task(restart)
    return {"status": "restarting"}

@app.get("/api/settings/storage", dependencies=[Depends(require_unlocked)])
def get_storage_settings():
    return {
        "config_dir": state.config_dir,
        "blob_dir": state.blob_dir
    }

@app.post("/api/settings/purge", dependencies=[Depends(require_unlocked)])
def purge_vault(req: PurgeRequest):
    # Security: Verify master password before destructive action
    try:
        with open(paths["salt"], "rb") as f:
            salt = f.read()
        # Check if password can derive a valid key (verify against salt)
        temp_security = VaultSecurity(req.password, salt, skip_validation=True)
        # Verify the key actually works by trying to decrypt the DB or just comparing with state.security
        if state.security and temp_security.key != state.security.key:
             raise HTTPException(status_code=401, detail="Invalid password")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid password")

    if req.purge_type == "mass":
        # Delete all files in mass storage
        files_dir = os.path.join(state.blob_dir, "files")
        if os.path.exists(files_dir):
            shutil.rmtree(files_dir)
            os.makedirs(files_dir, exist_ok=True)
        # Clear files in DB
        with state.db.session_scope() as session:
            session.query(DBFile).delete()
        return {"status": "mass_purge_complete"}
        
    elif req.purge_type == "everything":
        # WIPE EVERYTHING and LOCK
        # Delete DB, salt, certs, and mass storage
        shutil.rmtree(state.config_dir)
        shutil.rmtree(state.blob_dir)
        # Force immediate exit (user must restart)
        def self_destruct():
            time.sleep(1)
            os._exit(0)
        import threading
        threading.Timer(0.1, self_destruct).start()
        return {"status": "nuclear_purge_initiated"}

@app.post("/api/settings/export", dependencies=[Depends(require_unlocked)])
def export_vault(req: ExportRequest):
    # Security: Verify master password
    try:
        with open(paths["salt"], "rb") as f:
            salt = f.read()
        temp_security = VaultSecurity(req.password, salt, skip_validation=True)
        if state.security and temp_security.key != state.security.key:
             raise HTTPException(status_code=401, detail="Invalid password")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid password")

    target = os.path.abspath(req.target_path)
    if not os.path.exists(target):
        try:
            os.makedirs(target, exist_ok=True)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Cannot create target path: {str(e)}")

    with state.db.session_scope() as session:
        files = session.query(DBFile).all()
        count = 0
        for f in files:
            cat_name = f.category.name if f.category else "Uncategorized"
            # Sanitize names for folder structure
            def sanitize(s): return "".join([c for c in s if c.isalnum() or c in (' ', '_', '-')]).strip()
            
            clean_cat = sanitize(cat_name)
            # Use tag order defined by 'position' column (already handled by relationship order_by)
            tag_names = [sanitize(t.name) for t in f.tags if t]
            tag_path = os.path.join(*tag_names) if tag_names else ""
            
            dest_dir = os.path.join(target, clean_cat, tag_path)
            os.makedirs(dest_dir, exist_ok=True)
            
            # Final destination path
            dest_file = os.path.join(dest_dir, f.filename)
            
            # Decrypt and write to normal disk
            try:
                with open(dest_file, "wb") as out:
                    for chunk in state.vault.stream_file(f.id):
                        out.write(chunk)
                count += 1
            except Exception as e:
                state.logger.error(f"Export failed for {f.filename}: {e}")

    return {"status": "ok", "exported_count": count}

@app.get("/api/import/preview", dependencies=[Depends(require_unlocked)])
def import_preview(url: str):
    from .scrapers.ytdlp_engine import fetch_metadata
    meta = fetch_metadata(url)
    if not meta:
        raise HTTPException(status_code=400, detail="Failed to fetch metadata")
    return meta

def run_import_task(task_id: str, req: URLImportRequest):
    from .scrapers.ytdlp_engine import fetch_metadata, download_stream
    from .database import Tag as DBTag
    import requests
    import base64
    
    try:
        meta = fetch_metadata(req.url)
        if not meta:
            import_tasks[task_id] = {"status": "error", "error": "Failed to fetch metadata"}
            return
            
        if meta.get("is_playlist") and req.playlist_index is not None:
            target_entry = None
            for e in meta.get("entries", []):
                if e.get("playlist_index") == req.playlist_index:
                    target_entry = e
                    break
            if target_entry:
                meta = target_entry
            else:
                import_tasks[task_id] = {"status": "error", "error": "Playlist item not found"}
                return
        
        filename = req.filename or f"{meta.get('title', 'Unknown')}.{meta.get('ext', 'mp4')}"
        duration = meta.get('duration')
        
        # Download thumbnail if available
        thumbnail_b64 = None
        if meta.get('thumbnail_url'):
            try:
                r = requests.get(meta['thumbnail_url'], timeout=10)
                if r.ok:
                    thumbnail_b64 = f"data:{r.headers.get('Content-Type', 'image/jpeg')};base64,{base64.b64encode(r.content).decode('utf-8')}"
            except Exception as e:
                state.logger.warning(f"Failed to download thumbnail from {meta['thumbnail_url']}: {e}")
        
        temp_dir = os.path.join(state.config_dir, "temp")
        file_id, total_size = state.vault.store_file(download_stream(req.url, temp_dir, playlist_index=req.playlist_index))
        
        with db_write_lock:
            with state.db.session_scope() as session:
                # Handle tags
                tag_objs = []
                for tname in req.tags:
                    tname = tname.strip()
                    if not tname: continue
                    tag = session.query(DBTag).filter(DBTag.name == tname).first()
                    if not tag:
                        tag = DBTag(name=tname)
                        session.add(tag)
                        session.flush()
                    tag_objs.append(tag)
                
                db_file = DBFile(
                    id=file_id,
                    filename=filename,
                    size=total_size,
                    duration=duration,
                    category_id=req.category_id,
                    thumbnail_data=thumbnail_b64,
                    source_url=req.source_url or req.url,
                    artist=req.artist or meta.get('uploader')
                )
                if tag_objs:
                    db_file.tags = tag_objs
                    
                session.add(db_file)
            
        import_tasks[task_id] = {"status": "completed", "id": file_id, "filename": filename}
    except Exception as e:
        import_tasks[task_id] = {"status": "error", "error": str(e)}

@app.post("/api/import/url", dependencies=[Depends(require_unlocked)])
def import_url(req: URLImportRequest, background_tasks: BackgroundTasks):
    task_id = secrets.token_hex(8)
    import_tasks[task_id] = {"status": "downloading"}
    background_tasks.add_task(run_import_task, task_id, req)
    return {"task_id": task_id}

@app.get("/api/import/status/{task_id}", dependencies=[Depends(require_unlocked)])
def import_status(task_id: str):
    task = import_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.post("/api/files", dependencies=[Depends(require_unlocked)])
def upload_file(
    file: UploadFile, 
    thumbnail: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    tags: Optional[str] = Form(None), # Comma-separated or JSON list
    artist: Optional[str] = Form(None),
    source_url: Optional[str] = Form(None)
):
    temp_dir = os.path.join(state.config_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    ext = file.filename.split('.')[-1] if '.' in file.filename else 'tmp'
    temp_path = os.path.join(temp_dir, f"{secrets.token_hex(16)}.{ext}")
    
    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        duration = None
        if not thumbnail:
            thumbnail, duration = generate_thumbnail_from_file(temp_path, file.filename)
            
        creation_date = get_file_creation_date(temp_path)

        def file_iterator():
            with open(temp_path, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk: break
                    yield chunk

        file_id, total_size = state.vault.store_file(file_iterator())
        
        # Determine category
        final_category_id = category_id
        with db_write_lock:
            if not final_category_id:
                # Automatic categorization if none provided
                cat_name = "Other"
                ext_lower = ext.lower()
                if ext_lower in ['mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv']:
                    cat_name = "Video"
                elif ext_lower in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                    cat_name = "Image"
                elif ext_lower in ['pdf', 'txt', 'doc', 'docx']:
                    cat_name = "Document"

                with state.db.session_scope() as session:
                    category = session.query(DBCategory).filter(DBCategory.name == cat_name).first()
                    if not category:
                        category = DBCategory(name=cat_name)
                        session.add(category)
                        session.flush()
                    final_category_id = category.id

            # Handle tags
            tag_list = []
            if tags:
                try:
                    tag_list = json.loads(tags)
                except:
                    tag_list = [t.strip() for t in tags.split(',') if t.strip()]

            from .database import Tag as DBTag
            with state.db.session_scope() as session:
                tag_objs = []
                for tname in tag_list:
                    tag = session.query(DBTag).filter(DBTag.name == tname).first()
                    if not tag:
                        tag = DBTag(name=tname)
                        session.add(tag)
                        session.flush()
                    tag_objs.append(tag)
                
                db_file = DBFile(
                    id=file_id, 
                    filename=file.filename, 
                    size=total_size, 
                    duration=duration,
                    thumbnail_data=thumbnail,
                    category_id=final_category_id,
                    metadata_created_at=creation_date,
                    artist=artist,
                    source_url=source_url
                )
                if tag_objs:
                    db_file.tags = tag_objs
                session.add(db_file)
        
        return {"id": file_id, "filename": file.filename}
    finally:
        if os.path.exists(temp_path):
            file_size = os.path.getsize(temp_path)
            chunk_size = 1024 * 1024 # 1MB
            with open(temp_path, "wb") as f:
                remaining = file_size
                zeros = b'\0' * chunk_size
                while remaining > 0:
                    write_size = min(remaining, chunk_size)
                    f.write(zeros[:write_size])
                    remaining -= write_size
            os.remove(temp_path)

@app.get("/api/browse/folders", dependencies=[Depends(require_unlocked)])
def browse_folders():
    from .database import Category as DBCategory, Tag as DBTag
    with state.db.session_scope() as session:
        files = session.query(DBFile).all()
        root = {"name": "Root", "type": "folder", "children": {}}
        
        for f in files:
            cat_name = f.category.name if f.category else "Uncategorized"
            if cat_name not in root["children"]:
                root["children"][cat_name] = {"name": cat_name, "type": "folder", "children": {}, "files": []}
            
            curr = root["children"][cat_name]
            # Navigate/Build tag path
            for t in f.tags:
                if not t: continue
                if t.name not in curr["children"]:
                    curr["children"][t.name] = {"name": t.name, "type": "folder", "children": {}, "files": []}
                curr = curr["children"][t.name]
            
            # Add file to the leaf node
            if "files" not in curr: curr["files"] = []
            curr["files"].append({
                "id": f.id,
                "filename": f.filename,
                "thumbnail_data": f.thumbnail_data,
                "duration": f.duration,
                "is_favorite": bool(f.is_favorite)
            })
            
        return root

@app.get("/api/files", dependencies=[Depends(require_unlocked)])
def list_files(
    category_id: Optional[int] = None, 
    favorite: Optional[bool] = None,
    q: Optional[str] = None,
    sort_by: str = "date",
    sort_dir: str = "desc",
    page: int = 1,
    per_page: int = 50
):
    from .database import File as DBFile, Tag as DBTag, Category as DBCategory
    with state.db.session_scope() as session:
        query = session.query(DBFile)
        
        if category_id is not None:
            query = query.filter(DBFile.category_id == category_id)

        if favorite is True:
            query = query.filter(DBFile.is_favorite == 1)
            
        if q:
            criteria = SearchParser.parse(q)
            
            # Helper to apply include/exclude filters
            def apply_filter(q_obj, field_attr, terms, exclude=False):
                for term in terms:
                    if exclude:
                        q_obj = q_obj.filter(~field_attr.ilike(f"%{term}%"))
                    else:
                        q_obj = q_obj.filter(field_attr.ilike(f"%{term}%"))
                return q_obj

            # Support favorite:true in search string
            for term in criteria['any']['include']:
                if term.lower() == "favorite:true":
                    query = query.filter(DBFile.is_favorite == 1)
                elif term.lower() == "favorite:false":
                    query = query.filter(DBFile.is_favorite == 0)

            # Filter by name
            query = apply_filter(query, DBFile.filename, criteria['name']['include'])
            query = apply_filter(query, DBFile.filename, criteria['name']['exclude'], exclude=True)
            
            # Filter by category
            if criteria['cat']['include'] or criteria['cat']['exclude']:
                query = query.join(DBCategory, DBFile.category_id == DBCategory.id)
                query = apply_filter(query, DBCategory.name, criteria['cat']['include'])
                query = apply_filter(query, DBCategory.name, criteria['cat']['exclude'], exclude=True)
            
            # Filter by tags
            if criteria['tag']['include'] or criteria['tag']['exclude']:
                for term in criteria['tag']['include']:
                    query = query.filter(DBFile.tags.any(DBTag.name.ilike(f"%{term}%")))
                for term in criteria['tag']['exclude']:
                    query = query.filter(~DBFile.tags.any(DBTag.name.ilike(f"%{term}%")))
            
            # Filter by artist
            query = apply_filter(query, DBFile.artist, criteria['artist']['include'])
            query = apply_filter(query, DBFile.artist, criteria['artist']['exclude'], exclude=True)
            
            # Filter by site (source_url)
            query = apply_filter(query, DBFile.source_url, criteria['site']['include'])
            query = apply_filter(query, DBFile.source_url, criteria['site']['exclude'], exclude=True)

            # Filter by 'any' (name or tag or artist or site)
            for term in criteria['any']['include']:
                query = query.filter(
                    or_(
                        DBFile.filename.ilike(f"%{term}%"),
                        DBFile.tags.any(DBTag.name.ilike(f"%{term}%")),
                        DBFile.artist.ilike(f"%{term}%"),
                        DBFile.source_url.ilike(f"%{term}%")
                    )
                )
            for term in criteria['any']['exclude']:
                query = query.filter(
                    ~or_(
                        DBFile.filename.ilike(f"%{term}%"),
                        DBFile.tags.any(DBTag.name.ilike(f"%{term}%"))
                    )
                )

        # Sorting
        if sort_by == "name":
            query = query.order_by(DBFile.filename.asc() if sort_dir == "asc" else DBFile.filename.desc())
        elif sort_by == "size":
            query = query.order_by(DBFile.size.asc() if sort_dir == "asc" else DBFile.size.desc())
        elif sort_by == "duration":
            if sort_dir == "asc":
                query = query.order_by(DBFile.duration.asc().nulls_last())
            else:
                query = query.order_by(DBFile.duration.desc().nulls_last())
        elif sort_by == "created":
            if sort_dir == "asc":
                query = query.order_by(DBFile.metadata_created_at.asc().nulls_last())
            else:
                query = query.order_by(DBFile.metadata_created_at.desc().nulls_last())
        else: # Default: date added
            query = query.order_by(DBFile.added_at.asc() if sort_dir == "asc" else DBFile.added_at.desc())

        # Pagination
        total = query.count()
        files = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # If natural sort is requested, we do it in memory
        if sort_by == "name":
            files.sort(key=lambda f: natural_sort_key(f.filename), reverse=(sort_dir == "desc"))

        return {
            "results": [
                {
                    "id": f.id, 
                    "filename": f.filename, 
                    "category_id": f.category_id, 
                    "thumbnail_data": f.thumbnail_data,
                    "duration": f.duration,
                    "size": f.size,
                    "added_at": f.added_at.isoformat() if f.added_at else None,
                    "created_at": f.metadata_created_at.isoformat() if f.metadata_created_at else None,
                    "is_favorite": bool(f.is_favorite),
                    "notes": f.notes,
                    "artist": f.artist,
                    "source_url": f.source_url,
                    "tags": [t.name for t in f.tags if t]
                } for f in files
            ],
            "total": total,
            "page": page,
            "per_page": per_page
        }

@app.post("/api/files/{file_id}/tags", dependencies=[Depends(require_unlocked)])
def update_file_tags(file_id: str, req: UpdateTagsRequest):
    from .database import Tag as DBTag, file_tag_association
    from sqlalchemy import delete, insert
    with state.db.session_scope() as session:
        db_file = session.query(DBFile).filter(DBFile.id == file_id).first()
        if not db_file: raise HTTPException(status_code=404, detail="File not found")
        
        # Pre-load or create tags to get their IDs
        tag_objs = []
        for tag_name in req.tags:
            tag_name = tag_name.strip()
            if not tag_name: continue
            tag = session.query(DBTag).filter(DBTag.name == tag_name).first()
            if not tag:
                tag = DBTag(name=tag_name)
                session.add(tag)
                session.flush()
            tag_objs.append(tag)
        
        # Manually manage association to store 'position'
        session.execute(delete(file_tag_association).where(file_tag_association.c.file_id == file_id))
        for i, tag in enumerate(tag_objs):
            session.execute(insert(file_tag_association).values(
                file_id=file_id, 
                tag_id=tag.id, 
                position=i
            ))
            
    return {"status": "ok"}

@app.put("/api/tags/{old_name}", dependencies=[Depends(require_unlocked)])
def rename_tag(old_name: str, req: TagCreate):
    from .database import Tag as DBTag, file_tag_association
    from sqlalchemy import delete, insert, select
    new_name = req.name.strip()
    if not new_name: raise HTTPException(status_code=400, detail="New name required")
    
    with state.db.session_scope() as session:
        tag = session.query(DBTag).filter(DBTag.name == old_name).first()
        if not tag: raise HTTPException(status_code=404, detail="Tag not found")
        
        existing = session.query(DBTag).filter(DBTag.name == new_name).first()
        if existing:
            # Merge logic:
            # 1. Find all file IDs associated with the old tag
            file_ids = session.execute(
                select(file_tag_association.c.file_id).where(file_tag_association.c.tag_id == tag.id)
            ).scalars().all()
            
            # 2. For each file, ensure it has the new tag (ignore if already present)
            for fid in file_ids:
                has_new = session.execute(
                    select(file_tag_association).where(
                        file_tag_association.c.file_id == fid,
                        file_tag_association.c.tag_id == existing.id
                    )
                ).first()
                if not has_new:
                    session.execute(
                        insert(file_tag_association).values(file_id=fid, tag_id=existing.id)
                    )
            
            # 3. Remove old tag associations and the old tag itself
            session.execute(
                delete(file_tag_association).where(file_tag_association.c.tag_id == tag.id)
            )
            session.delete(tag)
        else:
            tag.name = new_name
            
    return {"status": "ok"}

@app.delete("/api/tags/{name}", dependencies=[Depends(require_unlocked)])
def delete_tag(name: str):
    from .database import Tag as DBTag, file_tag_association
    from sqlalchemy import delete
    with state.db.session_scope() as session:
        tag = session.query(DBTag).filter(DBTag.name == name).first()
        if not tag: raise HTTPException(status_code=404, detail="Tag not found")
        # Explicitly delete associations first to be safe
        session.execute(
            delete(file_tag_association).where(file_tag_association.c.tag_id == tag.id)
        )
        session.delete(tag)
    return {"status": "ok"}

@app.get("/api/tags", dependencies=[Depends(require_unlocked)])
def list_tags():
    from .database import Tag as DBTag
    with state.db.session_scope() as session:
        tags = session.query(DBTag).all()
        return [t.name for t in tags if t]

@app.get("/api/categories", dependencies=[Depends(require_unlocked)])
def list_categories():
    from .database import Category as DBCategory, File as DBFile
    from sqlalchemy import func
    with state.db.session_scope() as session:
        # Get counts for all categories
        counts = session.query(
            DBFile.category_id, func.count(DBFile.id)
        ).group_by(DBFile.category_id).all()
        count_map = {cat_id: count for cat_id, count in counts}

        categories = session.query(DBCategory).all()
        total_files = session.query(func.count(DBFile.id)).scalar()
        uncategorized_count = count_map.get(None, 0)
        favorites_count = session.query(func.count(DBFile.id)).filter(DBFile.is_favorite == 1).scalar()

        return {
            "categories": [
                {"id": c.id, "name": c.name, "count": count_map.get(c.id, 0)} 
                for c in categories if c
            ],
            "total": total_files,
            "uncategorized": uncategorized_count,
            "favorites": favorites_count
        }

@app.put("/api/categories/{cat_id}", dependencies=[Depends(require_unlocked)])
def rename_category(cat_id: int, req: CategoryCreate):
    from .database import Category as DBCategory
    new_name = req.name.strip()
    if not new_name: raise HTTPException(status_code=400, detail="Name required")
    
    with state.db.session_scope() as session:
        category = session.query(DBCategory).filter(DBCategory.id == cat_id).first()
        if not category: raise HTTPException(status_code=404, detail="Category not found")
        category.name = new_name
    return {"status": "ok"}

@app.delete("/api/categories/{cat_id}", dependencies=[Depends(require_unlocked)])
def delete_category(cat_id: int):
    from .database import Category as DBCategory, File as DBFile
    with state.db.session_scope() as session:
        category = session.query(DBCategory).filter(DBCategory.id == cat_id).first()
        if not category: raise HTTPException(status_code=404, detail="Category not found")
        
        # Move files to uncategorized (null) before deleting category
        session.query(DBFile).filter(DBFile.category_id == cat_id).update({DBFile.category_id: None})
        session.delete(category)
    return {"status": "ok"}

@app.post("/api/categories", dependencies=[Depends(require_unlocked)])
def create_category(cat: CategoryCreate):
    name = cat.name
    if not name: raise HTTPException(status_code=400, detail="Missing name")
    with state.db.session_scope() as session:
        existing = session.query(DBCategory).filter(DBCategory.name == name).first()
        if existing: raise HTTPException(status_code=400, detail="Category already exists")
        new_cat = DBCategory(name=name)
        session.add(new_cat)
        session.flush() # Get ID
        cat_id, cat_name = new_cat.id, new_cat.name
    return {"id": cat_id, "name": cat_name}

@app.put("/api/files/{file_id}/category", dependencies=[Depends(require_unlocked)])
def update_file_category(file_id: str, update: FileCategoryUpdate):
    cat_id = update.category_id
    with state.db.session_scope() as session:
        db_file = session.query(DBFile).filter(DBFile.id == file_id).first()
        if not db_file: raise HTTPException(status_code=404, detail="File not found")
        db_file.category_id = cat_id
    return {"status": "ok"}

@app.post("/api/files/{file_id}/favorite", dependencies=[Depends(require_unlocked)])
def toggle_favorite(file_id: str):
    with state.db.session_scope() as session:
        db_file = session.query(DBFile).filter(DBFile.id == file_id).first()
        if not db_file: raise HTTPException(status_code=404, detail="File not found")
        db_file.is_favorite = 0 if db_file.is_favorite else 1
        return {"status": "ok", "is_favorite": bool(db_file.is_favorite)}

@app.put("/api/files/{file_id}/metadata", dependencies=[Depends(require_unlocked)])
def update_metadata(file_id: str, req: FileMetadataUpdateRequest):
    with state.db.session_scope() as session:
        db_file = session.query(DBFile).filter(DBFile.id == file_id).first()
        if not db_file: raise HTTPException(status_code=404, detail="File not found")
        if req.notes is not None: db_file.notes = req.notes
        if req.artist is not None: db_file.artist = req.artist
        if req.source_url is not None: db_file.source_url = req.source_url
    return {"status": "ok"}

@app.put("/api/files/{file_id}/rename", dependencies=[Depends(require_unlocked)])
def rename_file(file_id: str, req: FileRenameRequest):
    filename = req.filename
    with state.db.session_scope() as session:
        db_file = session.query(DBFile).filter(DBFile.id == file_id).first()
        if not db_file: raise HTTPException(status_code=404, detail="File not found")
        db_file.filename = filename
    return {"status": "ok"}

@app.delete("/api/files/{file_id}", dependencies=[Depends(require_unlocked)])
def delete_file(file_id: str):
    with state.db.session_scope() as session:
        db_file = session.query(DBFile).filter(DBFile.id == file_id).first()
        if not db_file: raise HTTPException(status_code=404, detail="File not found")
        state.vault.delete_file(file_id)
        session.delete(db_file)
    return {"status": "ok"}

@app.get("/api/files/{file_id}", dependencies=[Depends(require_unlocked)])
def stream_file(file_id: str, request: Request):
    with state.db.session_scope() as session:
        db_file = session.query(DBFile).filter(DBFile.id == file_id).first()
        if not db_file: raise HTTPException(status_code=404, detail="File not found")
        file_size = getattr(db_file, 'size', 0)
        filename = db_file.filename

    try:
        range_header = request.headers.get('range')
        headers = {"Accept-Ranges": "bytes"}
        content_type, _ = mimetypes.guess_type(filename)
        content_type = content_type or "application/octet-stream"

        if range_header and file_size > 0:
            range_val = range_header.strip().replace("bytes=", "")
            start_str, end_str = range_val.split("-")
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
            if end >= file_size: end = file_size - 1
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            headers["Content-Length"] = str(end - start + 1)
            return StreamingResponse(state.vault.stream_file_range(file_id, start, end), status_code=206, headers=headers, media_type=content_type)
        else:
            if file_size > 0: headers["Content-Length"] = str(file_size)
            return StreamingResponse(state.vault.stream_file(file_id), headers=headers, media_type=content_type)
    except Exception as e:
        if state.logger: state.logger.error(f"Error streaming {file_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def start():
    import uvicorn
    from .security import generate_self_signed_cert
    
    # Reload paths based on potentially updated config_dir
    p = setup_vault_paths(state.config_dir or os.path.expanduser("~/.pandora"), state.blob_dir)
    cert_path, key_path = os.path.join(state.config_dir, "cert.pem"), os.path.join(state.config_dir, "key.pem")
    generate_self_signed_cert(cert_path, key_path)
    
    debug_mode = os.environ.get("PANDORA_DEBUG", "false").lower() == "true"
    # Show info logs by default so the user sees something in the terminal
    log_level = "info"
    
    config = uvicorn.Config(
        "pandora.backend.main:app", host="0.0.0.0", port=8000, 
        reload=debug_mode, ssl_keyfile=key_path, ssl_certfile=cert_path,
        log_level=log_level, log_config=None
    )
    server = uvicorn.Server(config)
    
    # Print startup message with links
    local_ip = get_local_ip()
    port = 8000
    print(f"\n" + "="*60)
    print(f"🚀 PANDORA IS RUNNING")
    print(f"Config: {state.config_dir}")
    print(f"Storage: {state.blob_dir}")
    print(f"-"*60)
    print(f"🔗 Local:   https://localhost:{port}")
    print(f"🌐 Network: https://{local_ip}:{port}")
    print(f"="*60 + "\n")

    def signal_handler(sig, frame):
        if state.logger: state.logger.info("Graceful shutdown initiated...")
        server.should_exit = True
        # Ensure we actually exit if uvicorn hangs
        threading.Timer(2.0, lambda: os._exit(0)).start()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    server.run()

import threading
if __name__ == "__main__":
    start()
