#!/usr/bin/env python3
"""
pandora.py - Self-Hosted Media & Link Management Platform

Kombiniert Funktionen von:
- Test_streaming_web_interface2.py (Streaming-Web-Oberfläche)
- file_tagger_gui_V5.2.py (Tagging und Dateiverwaltung)
Mit erweitertem Datenbankschema für URLs/Links
"""

import os
import sys
import sqlite3
import logging
import threading
import asyncio
import json
import time
import re
import mimetypes
import shutil
import subprocess
import queue
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse, quote, unquote

import aiohttp
from aiohttp import web
import aiofiles
import psutil

# Optional imports für erweiterte Funktionen
try:
    from send2trash import send2trash
    CAN_TRASH = True
except ImportError:
    CAN_TRASH = False

try:
    from hachoir.parser import createParser
    from hachoir.metadata import extractMetadata
    VIDEO_METADATA_AVAILABLE = True
except ImportError:
    VIDEO_METADATA_AVAILABLE = False

# Datenbank-Konfiguration
DB_DIR = Path.home() / '.pandora'
DB_PATH = DB_DIR / 'pandora.db'

# Web Server Konfiguration
HOST = '0.0.0.0'
PORT = 8080
CHUNK_SIZE = 64 * 1024  # 64 KB

# Erweiterte MIME-Type Erkennung
MIME_EXTENSIONS = {
    '.mp4': 'video/mp4',
    '.avi': 'video/x-msvideo',
    '.mov': 'video/quicktime',
    '.mkv': 'video/x-matroska',
    '.webm': 'video/webm',
    '.flv': 'video/x-flv',
    '.wmv': 'video/x-ms-wmv',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.bmp': 'image/bmp',
    '.svg': 'image/svg+xml',
}

# Datenbank-Schema
SCHEMA = """
-- Basistabelle für alle Einträge (Dateien und URLs)
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,  -- 'file', 'url', 'list'
    title TEXT,
    path TEXT,           -- Lokaler Pfad oder URL
    description TEXT,
    thumbnail_path TEXT,
    file_size INTEGER DEFAULT 0,
    duration FLOAT,
    added_at TEXT NOT NULL,
    modified_at TEXT NOT NULL,
    accessed_at TEXT,
    metadata_json TEXT DEFAULT '{}',
    UNIQUE(path) ON CONFLICT IGNORE
);

-- Tags/Kategorien
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    category TEXT DEFAULT 'general',
    color TEXT,
    global_rank INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

-- Verknüpfung zwischen Items und Tags
CREATE TABLE IF NOT EXISTS item_tags (
    item_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    rank INTEGER DEFAULT 0,
    added_at TEXT NOT NULL,
    PRIMARY KEY (item_id, tag_id),
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- Benutzerdefinierte Listen/Favoriten
CREATE TABLE IF NOT EXISTS custom_lists (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    is_encrypted INTEGER DEFAULT 0,
    encryption_key TEXT,
    created_at TEXT NOT NULL,
    modified_at TEXT NOT NULL
);

-- Items in Listen
CREATE TABLE IF NOT EXISTS list_items (
    list_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    rank INTEGER DEFAULT 0,
    added_at TEXT NOT NULL,
    notes TEXT,
    PRIMARY KEY (list_id, item_id),
    FOREIGN KEY (list_id) REFERENCES custom_lists(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

-- Watch-Verzeichnisse für automatisches Hinzufügen
CREATE TABLE IF NOT EXISTS watch_roots (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    recursive INTEGER DEFAULT 1,
    enabled INTEGER DEFAULT 1,
    added_at TEXT NOT NULL
);

-- Download-Queue für URLs
CREATE TABLE IF NOT EXISTS download_queue (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL,
    item_id INTEGER,  -- Verknüpfung mit items Tabelle
    status TEXT DEFAULT 'pending',  -- pending, downloading, completed, failed
    download_path TEXT,
    progress FLOAT DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE SET NULL
);

-- Indexe für Performance
CREATE INDEX IF NOT EXISTS idx_items_type ON items(type);
CREATE INDEX IF NOT EXISTS idx_items_added ON items(added_at);
CREATE INDEX IF NOT EXISTS idx_item_tags_item ON item_tags(item_id);
CREATE INDEX IF NOT EXISTS idx_item_tags_tag ON item_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_download_queue_status ON download_queue(status);
"""

@dataclass
class PandoraItem:
    """Repräsentiert einen Eintrag in Pandora (Datei, URL oder Liste)"""
    id: int
    type: str  # 'file', 'url', 'list'
    title: str
    path: str
    description: Optional[str] = None
    thumbnail_path: Optional[str] = None
    file_size: int = 0
    duration: Optional[float] = None
    added_at: Optional[str] = None
    modified_at: Optional[str] = None
    accessed_at: Optional[str] = None
    metadata: Dict[str, Any] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.tags is None:
            self.tags = []

class PandoraServer:
    """Hauptklasse für den Pandora-Server"""
    
    def __init__(self):
        self.app = web.Application(middlewares=[self.error_middleware])
        self.setup_logging()
        self.setup_database()
        self.setup_routes()
        
        # State Management
        self.is_running = False
        self.runner = None
        self.site = None
        self.start_time = time.time()
        
        # Watch Thread Management
        self.watch_stop_event = threading.Event()
        self.watch_thread = None
        self.watch_queue = queue.Queue()
        
        # Download Management
        self.download_stop_event = threading.Event()
        self.download_thread = None
        
        # Initialisiere Listen
        self.lists = {}
        self.load_lists()
        
    def setup_logging(self):
        """Setup für erweiterte Logging-Funktionalität"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('pandora_server.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger('Pandora')
        
    def setup_database(self):
        """Datenbank-Verbindung und Schema setup"""
        DB_DIR.mkdir(parents=True, exist_ok=True)
        
        conn = self.get_db_connection()
        try:
            # Erstelle alle Tabellen
            conn.executescript(SCHEMA)
            conn.commit()
            
            # Teste die Verbindung
            cur = conn.execute('SELECT COUNT(*) as count FROM items')
            count = cur.fetchone()['count']
            self.logger.info(f"Datenbank initialisiert, enthält {count} Einträge")
            
        except Exception as e:
            self.logger.error(f"Datenbank-Fehler: {e}")
            raise
        finally:
            conn.close()
            
    def setup_routes(self):
        """Setup aller Web-Routen"""
        # Statische Dateien
        self.app.router.add_static('/static', 'static', follow_symlinks=True)
        
        # Haupt-Routen
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/browse', self.handle_browse)
        self.app.router.add_get('/search', self.handle_search)
        self.app.router.add_get('/media/{item_id}', self.handle_media)
        self.app.router.add_get('/url/{item_id}', self.handle_url_view)
        self.app.router.add_get('/stream/{item_id}', self.handle_stream)
        self.app.router.add_get('/thumbnail/{item_id}', self.handle_thumbnail)
        
        # API Endpoints
        self.app.router.add_get('/api/items', self.handle_api_items)
        self.app.router.add_post('/api/items', self.handle_api_add_item)
        self.app.router.add_delete('/api/items/{item_id}', self.handle_api_delete_item)
        self.app.router.add_get('/api/items/{item_id}', self.handle_api_get_item)
        self.app.router.add_put('/api/items/{item_id}', self.handle_api_update_item)
        
        self.app.router.add_get('/api/search', self.handle_api_search)
        self.app.router.add_get('/api/tags', self.handle_api_tags)
        self.app.router.add_post('/api/tags', self.handle_api_add_tag)
        self.app.router.add_delete('/api/tags/{tag_id}', self.handle_api_delete_tag)
        self.app.router.add_put('/api/tags/{tag_id}', self.handle_api_update_tag)
        
        self.app.router.add_get('/api/lists', self.handle_api_lists)
        self.app.router.add_post('/api/lists', self.handle_api_create_list)
        self.app.router.add_delete('/api/lists/{list_id}', self.handle_api_delete_list)
        self.app.router.add_get('/api/lists/{list_id}/items', self.handle_api_list_items)
        self.app.router.add_post('/api/lists/{list_id}/items', self.handle_api_add_to_list)
        self.app.router.add_delete('/api/lists/{list_id}/items/{item_id}', self.handle_api_remove_from_list)
        
        self.app.router.add_get('/api/stats', self.handle_api_stats)
        self.app.router.add_post('/api/batch/tag', self.handle_api_batch_tag)
        self.app.router.add_post('/api/auto-tag', self.handle_api_auto_tag)
        
        # Watch-Verzeichnisse
        self.app.router.add_get('/api/watch', self.handle_api_get_watch)
        self.app.router.add_post('/api/watch', self.handle_api_add_watch)
        self.app.router.add_delete('/api/watch/{watch_id}', self.handle_api_remove_watch)
        self.app.router.add_post('/api/watch/start', self.handle_api_start_watch)
        self.app.router.add_post('/api/watch/stop', self.handle_api_stop_watch)
        
        # Downloads
        self.app.router.add_get('/api/downloads', self.handle_api_downloads)
        self.app.router.add_post('/api/downloads', self.handle_api_add_download)
        self.app.router.add_post('/api/downloads/{download_id}/cancel', self.handle_api_cancel_download)
        
        # Admin
        self.app.router.add_post('/api/admin/restart', self.handle_api_restart)
        self.app.router.add_post('/api/admin/shutdown', self.handle_api_shutdown)
        
        # Drag & Drop Upload
        self.app.router.add_post('/api/upload', self.handle_api_upload)
        
    # ==================== Datenbank Methoden ====================
    
    def get_db_connection(self) -> sqlite3.Connection:
        """Datenbank-Verbindung erstellen"""
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn
    
    # ==================== Item Management ====================
    
    def add_item(self, conn: sqlite3.Connection, item_data: Dict[str, Any]) -> int:
        """Fügt einen neuen Eintrag hinzu (Datei oder URL)"""
        now = datetime.now().isoformat()
        
        # Bestimme Typ basierend auf Pfad/URL
        path = item_data.get('path', '')
        if path.startswith(('http://', 'https://', 'ftp://')):
            item_type = 'url'
        else:
            item_type = 'file'
            
        # Extrahiere Metadaten
        metadata = item_data.get('metadata', {})
        
        # Für Dateien: Dateigröße und Typ ermitteln
        if item_type == 'file':
            file_path = Path(path)
            if file_path.exists():
                metadata['file_size'] = file_path.stat().st_size
                metadata['file_type'] = self.get_file_type(file_path)
                
                # Versuche Videolänge zu ermitteln
                if metadata['file_type'] == 'video':
                    duration = self.get_video_duration(file_path)
                    if duration:
                        metadata['duration'] = duration
        
        # Für URLs: Domain extrahieren
        else:
            try:
                parsed = urlparse(path)
                metadata['domain'] = parsed.netloc
                metadata['protocol'] = parsed.scheme
            except:
                pass
        
        # Tags verarbeiten
        tags = item_data.get('tags', [])
        
        with conn:
            # Füge Item hinzu
            cur = conn.execute('''
                INSERT INTO items (type, title, path, description, thumbnail_path,
                                 file_size, duration, added_at, modified_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item_type,
                item_data.get('title', Path(path).name if item_type == 'file' else path),
                path,
                item_data.get('description'),
                item_data.get('thumbnail_path'),
                metadata.get('file_size', 0),
                metadata.get('duration'),
                now,
                now,
                json.dumps(metadata)
            ))
            
            item_id = cur.lastrowid
            
            # Tags hinzufügen
            for tag_name in tags:
                tag_id = self._get_or_create_tag(conn, tag_name)
                conn.execute('''
                    INSERT OR IGNORE INTO item_tags (item_id, tag_id, added_at)
                    VALUES (?, ?, ?)
                ''', (item_id, tag_id, now))
                
        return item_id
    
    def get_item(self, conn: sqlite3.Connection, item_id: int) -> Optional[PandoraItem]:
        """Holt einen Eintrag anhand der ID"""
        cur = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,))
        row = cur.fetchone()
        
        if not row:
            return None
            
        # Tags für diesen Eintrag holen
        tag_cur = conn.execute('''
            SELECT t.name FROM tags t
            JOIN item_tags it ON t.id = it.tag_id
            WHERE it.item_id = ?
            ORDER BY it.rank
        ''', (item_id,))
        
        tags = [r['name'] for r in tag_cur.fetchall()]
        
        # Metadaten parsen
        metadata = {}
        if row['metadata_json']:
            try:
                metadata = json.loads(row['metadata_json'])
            except:
                pass
                
        return PandoraItem(
            id=row['id'],
            type=row['type'],
            title=row['title'] or '',
            path=row['path'],
            description=row['description'],
            thumbnail_path=row['thumbnail_path'],
            file_size=row['file_size'] or 0,
            duration=row['duration'],
            added_at=row['added_at'],
            modified_at=row['modified_at'],
            accessed_at=row['accessed_at'],
            metadata=metadata,
            tags=tags
        )
    
    def update_item(self, conn: sqlite3.Connection, item_id: int, updates: Dict[str, Any]) -> bool:
        """Aktualisiert einen Eintrag"""
        now = datetime.now().isoformat()
        
        # Baue UPDATE Query dynamisch auf
        set_clauses = []
        params = []
        
        for key, value in updates.items():
            if key == 'tags':
                continue  # Tags separat behandeln
            set_clauses.append(f"{key} = ?")
            params.append(value)
            
        if set_clauses:
            set_clauses.append("modified_at = ?")
            params.append(now)
            
            params.append(item_id)
            
            with conn:
                conn.execute(f'''
                    UPDATE items 
                    SET {', '.join(set_clauses)}
                    WHERE id = ?
                ''', params)
                
        # Tags aktualisieren
        if 'tags' in updates:
            self._update_item_tags(conn, item_id, updates['tags'])
            
        return True
    
    def delete_item(self, conn: sqlite3.Connection, item_id: int) -> bool:
        """Löscht einen Eintrag"""
        with conn:
            # Hole den Eintrag zuerst
            cur = conn.execute('SELECT type, path FROM items WHERE id = ?', (item_id,))
            row = cur.fetchone()
            
            if not row:
                return False
                
            # Optional: Datei in den Papierkorb verschieben
            if row['type'] == 'file':
                file_path = Path(row['path'])
                if file_path.exists():
                    try:
                        if CAN_TRASH:
                            send2trash(str(file_path))
                        else:
                            file_path.unlink()
                    except Exception as e:
                        self.logger.warning(f"Could not delete file {file_path}: {e}")
            
            # Lösche aus der Datenbank
            conn.execute('DELETE FROM items WHERE id = ?', (item_id,))
            
        return True
    
    # ==================== Tag Management ====================
    
    def _get_or_create_tag(self, conn: sqlite3.Connection, tag_name: str) -> int:
        """Holt oder erstellt einen Tag"""
        tag_name = tag_name.strip().lower()
        if not tag_name:
            return 0
            
        cur = conn.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
        row = cur.fetchone()
        
        if row:
            return row['id']
            
        # Neuer Tag
        now = datetime.now().isoformat()
        cur = conn.execute('''
            INSERT INTO tags (name, created_at)
            VALUES (?, ?)
        ''', (tag_name, now))
        
        return cur.lastrowid
    
    def _update_item_tags(self, conn: sqlite3.Connection, item_id: int, tags: List[str]):
        """Aktualisiert die Tags eines Eintrags"""
        now = datetime.now().isoformat()
        
        with conn:
            # Alte Tags entfernen
            conn.execute('DELETE FROM item_tags WHERE item_id = ?', (item_id,))
            
            # Neue Tags hinzufügen
            for idx, tag_name in enumerate(tags):
                tag_id = self._get_or_create_tag(conn, tag_name)
                conn.execute('''
                    INSERT INTO item_tags (item_id, tag_id, rank, added_at)
                    VALUES (?, ?, ?, ?)
                ''', (item_id, tag_id, idx, now))
    
    # ==================== Listen Management ====================
    
    def load_lists(self):
        """Lädt benutzerdefinierte Listen"""
        lists_file = DB_DIR / 'lists.json'
        if lists_file.exists():
            try:
                with open(lists_file, 'r', encoding='utf-8') as f:
                    self.lists = json.load(f)
            except Exception as e:
                self.logger.error(f"Fehler beim Laden der Listen: {e}")
                self.lists = {}
        else:
            self.lists = {}
    
    def save_lists(self):
        """Speichert benutzerdefinierte Listen"""
        lists_file = DB_DIR / 'lists.json'
        try:
            with open(lists_file, 'w', encoding='utf-8') as f:
                json.dump(self.lists, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Fehler beim Speichern der Listen: {e}")
    
    # ==================== Watch-Verzeichnisse ====================
    
    def start_watch(self):
        """Startet das Überwachen von Verzeichnissen"""
        if self.watch_thread and self.watch_thread.is_alive():
            return
            
        self.watch_stop_event.clear()
        self.watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.watch_thread.start()
        self.logger.info("Watch-Thread gestartet")
    
    def stop_watch(self):
        """Stoppt das Überwachen von Verzeichnissen"""
        self.watch_stop_event.set()
        if self.watch_thread:
            self.watch_thread.join(timeout=5.0)
            self.logger.info("Watch-Thread gestoppt")
    
    def _watch_loop(self):
        """Hauptloop für Watch-Verzeichnisse"""
        while not self.watch_stop_event.is_set():
            conn = self.get_db_connection()
            try:
                # Hole aktive Watch-Verzeichnisse
                cur = conn.execute('SELECT path, recursive FROM watch_roots WHERE enabled = 1')
                watch_roots = cur.fetchall()
                
                for root in watch_roots:
                    root_path = Path(root['path'])
                    if not root_path.exists():
                        continue
                        
                    # Finde neue Dateien
                    if root['recursive']:
                        files = list(root_path.rglob('*'))
                    else:
                        files = list(root_path.glob('*'))
                    
                    new_files = []
                    for file_path in files:
                        if file_path.is_file():
                            # Prüfe ob Datei bereits in der DB ist
                            cur = conn.execute('SELECT id FROM items WHERE path = ?', (str(file_path),))
                            if not cur.fetchone():
                                new_files.append(file_path)
                    
                    # Füge neue Dateien hinzu
                    for file_path in new_files:
                        try:
                            item_id = self.add_item(conn, {
                                'path': str(file_path),
                                'title': file_path.name,
                                'type': 'file'
                            })
                            self.logger.info(f"Auto-added file: {file_path}")
                            self.watch_queue.put(('new_file', item_id, str(file_path)))
                        except Exception as e:
                            self.logger.error(f"Error auto-adding file {file_path}: {e}")
                
            except Exception as e:
                self.logger.error(f"Error in watch loop: {e}")
            finally:
                conn.close()
            
            # Warte 60 Sekunden oder bis Stop-Event
            for _ in range(60):
                if self.watch_stop_event.is_set():
                    break
                time.sleep(1)
    
    # ==================== Hilfsmethoden ====================
    
    def get_file_type(self, file_path: Path) -> str:
        """Bestimmt den Dateityp"""
        ext = file_path.suffix.lower()
        video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'}
        image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}
        
        if ext in video_exts:
            return 'video'
        elif ext in image_exts:
            return 'image'
        elif ext in {'.txt', '.pdf', '.doc', '.docx'}:
            return 'document'
        else:
            return 'other'
    
    def get_video_duration(self, file_path: Path) -> Optional[float]:
        """Extrahiert die Videolänge"""
        if not VIDEO_METADATA_AVAILABLE:
            return None
            
        try:
            parser = createParser(str(file_path))
            if not parser:
                return None
                
            metadata = extractMetadata(parser)
            if metadata and hasattr(metadata, 'duration'):
                return metadata.duration.seconds
        except Exception:
            pass
            
        return None
    
    def get_mime_type(self, file_path: Path) -> str:
        """Bestimmt MIME-Type"""
        ext = file_path.suffix.lower()
        if ext in MIME_EXTENSIONS:
            return MIME_EXTENSIONS[ext]
        
        mime_type = mimetypes.guess_type(str(file_path))[0]
        return mime_type or 'application/octet-stream'
    
    def format_file_size(self, size_bytes: int) -> str:
        """Formatiert Dateigröße für Anzeige"""
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def item_to_dict(self, item: PandoraItem) -> Dict[str, Any]:
        """Konvertiert PandoraItem zu Dictionary"""
        mime_type = 'text/html' if item.type == 'url' else self.get_mime_type(Path(item.path))
        
        result = {
            'id': item.id,
            'type': item.type,
            'title': item.title,
            'path': item.path,
            'description': item.description,
            'thumbnail_path': item.thumbnail_path,
            'file_size': item.file_size,
            'file_size_formatted': self.format_file_size(item.file_size) if item.type == 'file' else '',
            'duration': item.duration,
            'duration_formatted': self.format_duration(item.duration) if item.duration else '',
            'added_at': item.added_at,
            'modified_at': item.modified_at,
            'tags': item.tags,
            'mime_type': mime_type,
            'stream_url': f'/stream/{item.id}' if item.type == 'file' else None,
            'view_url': f'/media/{item.id}' if item.type == 'file' else f'/url/{item.id}',
            'metadata': item.metadata
        }
        
        return result
    
    def format_duration(self, seconds: float) -> str:
        """Formatiert Dauer für Anzeige"""
        if not seconds:
            return ""
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    # ==================== API Handlers ====================
    
    @web.middleware
    async def error_middleware(self, request, handler):
        """Globale Fehlerbehandlung"""
        try:
            response = await handler(request)
            return response
        except web.HTTPException as ex:
            return web.json_response({
                'error': ex.reason,
                'status': ex.status
            }, status=ex.status)
        except Exception as e:
            self.logger.error(f"Unbehandelter Fehler: {e}")
            return web.json_response({
                'error': 'Interner Server Fehler',
                'details': str(e)
            }, status=500)
    
    async def handle_index(self, request):
        """Hauptseite"""
        return await self.render_template('index.html')
    
    async def handle_browse(self, request):
        """Browse-Seite"""
        return await self.render_template('browse.html')
    
    async def handle_search(self, request):
        """Suchseite"""
        return await self.render_template('search.html')
    
    async def handle_media(self, request):
        """Medien-Viewer Seite"""
        item_id = request.match_info['item_id']
        conn = self.get_db_connection()
        try:
            item = self.get_item(conn, int(item_id))
            if not item:
                raise web.HTTPNotFound()
                
            if item.type != 'file':
                raise web.HTTPBadRequest(text="Keine Datei")
                
            return await self.render_template('media.html', {
                'item': self.item_to_dict(item),
                'item_json': json.dumps(self.item_to_dict(item))
            })
        finally:
            conn.close()
    
    async def handle_url_view(self, request):
        """URL-Viewer Seite"""
        item_id = request.match_info['item_id']
        conn = self.get_db_connection()
        try:
            item = self.get_item(conn, int(item_id))
            if not item:
                raise web.HTTPNotFound()
                
            if item.type != 'url':
                raise web.HTTPBadRequest(text="Keine URL")
                
            return await self.render_template('url_view.html', {
                'item': self.item_to_dict(item),
                'item_json': json.dumps(self.item_to_dict(item))
            })
        finally:
            conn.close()
    
    async def handle_stream(self, request):
        """Streaming Handler"""
        item_id = request.match_info['item_id']
        conn = self.get_db_connection()
        
        try:
            item = self.get_item(conn, int(item_id))
            if not item or item.type != 'file':
                raise web.HTTPNotFound()
                
            file_path = Path(item.path)
            if not file_path.exists():
                raise web.HTTPNotFound(text="Datei existiert nicht")
                
            range_header = request.headers.get('Range')
            file_size = file_path.stat().st_size
            
            return await self.stream_file(request, file_path, range_header, file_size)
            
        finally:
            conn.close()
    
    async def handle_thumbnail(self, request):
        """Thumbnail Handler"""
        item_id = request.match_info['item_id']
        # TODO: Thumbnail-Generierung implementieren
        raise web.HTTPNotImplemented()
    
    async def stream_file(self, request, file_path: Path, range_header: Optional[str], file_size: int):
        """Streamt eine Datei"""
        mime_type = self.get_mime_type(file_path)
        start = 0
        end = file_size - 1
        
        if range_header:
            m = re.match(r'bytes=(\d*)-(\d*)', range_header)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                if m.group(2):
                    end = int(m.group(2))
                start = max(0, min(start, file_size - 1))
                end = max(start, min(end, file_size - 1))
        
        length = end - start + 1
        headers = {
            'Accept-Ranges': 'bytes',
            'Content-Length': str(length),
            'Content-Type': mime_type,
            'Cache-Control': 'no-cache',
        }
        status = 200
        if range_header:
            headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            status = 206
        
        resp = web.StreamResponse(status=status, headers=headers)
        await resp.prepare(request)
        
        try:
            async with aiofiles.open(file_path, 'rb') as fh:
                await fh.seek(start)
                remaining = length
                while remaining > 0:
                    read_size = min(CHUNK_SIZE, remaining)
                    chunk = await fh.read(read_size)
                    if not chunk:
                        break
                    await resp.write(chunk)
                    try:
                        await resp.drain()
                    except (ConnectionResetError, asyncio.CancelledError):
                        break
                    remaining -= len(chunk)
        except Exception as e:
            self.logger.error(f"Streaming error: {e}")
        finally:
            try:
                await resp.write_eof()
            except Exception:
                pass
        
        return resp
    
    async def handle_api_items(self, request):
        """API: Holt Einträge"""
        page = int(request.query.get('page', 1))
        per_page = int(request.query.get('per_page', 24))
        item_type = request.query.get('type', '')
        tag = request.query.get('tag', '')
        sort_by = request.query.get('sort_by', 'added_at')
        sort_dir = request.query.get('sort_dir', 'desc')
        
        conn = self.get_db_connection()
        try:
            # Baue Query auf
            query = '''
                SELECT i.*, GROUP_CONCAT(t.name, '||') as tags_concat
                FROM items i
                LEFT JOIN item_tags it ON i.id = it.item_id
                LEFT JOIN tags t ON it.tag_id = t.id
            '''
            
            where_clauses = []
            params = []
            
            if item_type:
                where_clauses.append('i.type = ?')
                params.append(item_type)
                
            if tag:
                where_clauses.append('i.id IN (SELECT item_id FROM item_tags WHERE tag_id = (SELECT id FROM tags WHERE name = ?))')
                params.append(tag)
            
            if where_clauses:
                query += ' WHERE ' + ' AND '.join(where_clauses)
                
            query += ' GROUP BY i.id'
            
            # Sortierung
            if sort_by in ['added_at', 'modified_at', 'title']:
                query += f' ORDER BY i.{sort_by} {sort_dir.upper()}'
            else:
                query += ' ORDER BY i.added_at DESC'
            
            # Pagination
            offset = (page - 1) * per_page
            query += ' LIMIT ? OFFSET ?'
            params.extend([per_page, offset])
            
            cur = conn.execute(query, params)
            rows = cur.fetchall()
            
            # Gesamtzahl für Pagination
            count_query = 'SELECT COUNT(DISTINCT i.id) as total FROM items i'
            if where_clauses:
                count_query += ' WHERE ' + ' AND '.join(where_clauses)
            
            count_cur = conn.execute(count_query, params[:-2] if len(params) > 2 else [])
            total = count_cur.fetchone()['total']
            
            # Konvertiere zu PandoraItem
            items = []
            for row in rows:
                tags = []
                if row['tags_concat']:
                    tags = [t for t in row['tags_concat'].split('||') if t]
                
                metadata = {}
                if row['metadata_json']:
                    try:
                        metadata = json.loads(row['metadata_json'])
                    except:
                        pass
                
                item = PandoraItem(
                    id=row['id'],
                    type=row['type'],
                    title=row['title'] or '',
                    path=row['path'],
                    description=row['description'],
                    thumbnail_path=row['thumbnail_path'],
                    file_size=row['file_size'] or 0,
                    duration=row['duration'],
                    added_at=row['added_at'],
                    modified_at=row['modified_at'],
                    accessed_at=row['accessed_at'],
                    metadata=metadata,
                    tags=tags
                )
                items.append(item)
            
            return web.json_response({
                'items': [self.item_to_dict(item) for item in items],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            })
            
        finally:
            conn.close()
    
    async def handle_api_add_item(self, request):
        """API: Fügt neuen Eintrag hinzu"""
        data = await request.json()
        
        conn = self.get_db_connection()
        try:
            item_id = self.add_item(conn, data)
            
            # Automatisches Tagging
            if data.get('auto_tag', True):
                await self.auto_tag_item(conn, item_id)
            
            item = self.get_item(conn, item_id)
            return web.json_response({
                'success': True,
                'item': self.item_to_dict(item)
            })
            
        except Exception as e:
            return web.json_response({
                'success': False,
                'error': str(e)
            }, status=400)
        finally:
            conn.close()
    
    async def handle_api_get_item(self, request):
        """API: Holt einzelnen Eintrag"""
        item_id = int(request.match_info['item_id'])
        
        conn = self.get_db_connection()
        try:
            item = self.get_item(conn, item_id)
            if not item:
                raise web.HTTPNotFound()
                
            return web.json_response(self.item_to_dict(item))
        finally:
            conn.close()
    
    async def handle_api_update_item(self, request):
        """API: Aktualisiert Eintrag"""
        item_id = int(request.match_info['item_id'])
        data = await request.json()
        
        conn = self.get_db_connection()
        try:
            success = self.update_item(conn, item_id, data)
            if not success:
                raise web.HTTPNotFound()
                
            item = self.get_item(conn, item_id)
            return web.json_response({
                'success': True,
                'item': self.item_to_dict(item)
            })
        finally:
            conn.close()
    
    async def handle_api_delete_item(self, request):
        """API: Löscht Eintrag"""
        item_id = int(request.match_info['item_id'])
        
        conn = self.get_db_connection()
        try:
            success = self.delete_item(conn, item_id)
            return web.json_response({'success': success})
        finally:
            conn.close()
    
    async def handle_api_search(self, request):
        """API: Erweiterte Suche"""
        query = request.query.get('q', '')
        item_type = request.query.get('type', '')
        tag = request.query.get('tag', '')
        page = int(request.query.get('page', 1))
        per_page = int(request.query.get('per_page', 24))
        
        conn = self.get_db_connection()
        try:
            # TODO: Erweiterte Suchlogik implementieren
            # Für jetzt einfache Suche im Titel und Pfad
            search_query = '''
                SELECT i.*, GROUP_CONCAT(t.name, '||') as tags_concat
                FROM items i
                LEFT JOIN item_tags it ON i.id = it.item_id
                LEFT JOIN tags t ON it.tag_id = t.id
                WHERE (i.title LIKE ? OR i.path LIKE ? OR i.description LIKE ?)
            '''
            
            params = [f'%{query}%', f'%{query}%', f'%{query}%']
            
            if item_type:
                search_query += ' AND i.type = ?'
                params.append(item_type)
                
            if tag:
                search_query += ' AND i.id IN (SELECT item_id FROM item_tags WHERE tag_id = (SELECT id FROM tags WHERE name = ?))'
                params.append(tag)
            
            search_query += ' GROUP BY i.id ORDER BY i.added_at DESC'
            
            # Pagination
            offset = (page - 1) * per_page
            search_query += ' LIMIT ? OFFSET ?'
            params.extend([per_page, offset])
            
            cur = conn.execute(search_query, params)
            rows = cur.fetchall()
            
            # Konvertiere zu PandoraItem
            items = []
            for row in rows:
                tags = []
                if row['tags_concat']:
                    tags = [t for t in row['tags_concat'].split('||') if t]
                
                metadata = {}
                if row['metadata_json']:
                    try:
                        metadata = json.loads(row['metadata_json'])
                    except:
                        pass
                
                item = PandoraItem(
                    id=row['id'],
                    type=row['type'],
                    title=row['title'] or '',
                    path=row['path'],
                    description=row['description'],
                    thumbnail_path=row['thumbnail_path'],
                    file_size=row['file_size'] or 0,
                    duration=row['duration'],
                    added_at=row['added_at'],
                    modified_at=row['modified_at'],
                    accessed_at=row['accessed_at'],
                    metadata=metadata,
                    tags=tags
                )
                items.append(item)
            
            return web.json_response({
                'results': [self.item_to_dict(item) for item in items],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': len(items),  # Vereinfacht, sollte eig. total_count sein
                    'pages': 1
                }
            })
            
        finally:
            conn.close()
    
    async def handle_api_tags(self, request):
        """API: Holt alle Tags"""
        conn = self.get_db_connection()
        try:
            cur = conn.execute('SELECT id, name, category, color FROM tags ORDER BY name')
            tags = [dict(row) for row in cur.fetchall()]
            return web.json_response({'tags': tags})
        finally:
            conn.close()
    
    async def handle_api_add_tag(self, request):
        """API: Fügt neuen Tag hinzu"""
        data = await request.json()
        tag_name = data.get('name', '').strip()
        
        if not tag_name:
            return web.json_response({'error': 'Tag name required'}, status=400)
        
        conn = self.get_db_connection()
        try:
            now = datetime.now().isoformat()
            cur = conn.execute('INSERT OR IGNORE INTO tags (name, created_at) VALUES (?, ?)', (tag_name, now))
            
            if cur.lastrowid:
                tag_id = cur.lastrowid
            else:
                cur = conn.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
                tag_id = cur.fetchone()['id']
                
            return web.json_response({'success': True, 'tag_id': tag_id})
        finally:
            conn.close()
    
    async def handle_api_batch_tag(self, request):
        """API: Taggt mehrere Einträge auf einmal"""
        data = await request.json()
        item_ids = data.get('item_ids', [])
        tags = data.get('tags', [])
        
        if not item_ids or not tags:
            return web.json_response({'error': 'item_ids and tags required'}, status=400)
        
        conn = self.get_db_connection()
        try:
            now = datetime.now().isoformat()
            
            for item_id in item_ids:
                for tag_name in tags:
                    tag_id = self._get_or_create_tag(conn, tag_name)
                    conn.execute('''
                        INSERT OR IGNORE INTO item_tags (item_id, tag_id, added_at)
                        VALUES (?, ?, ?)
                    ''', (item_id, tag_id, now))
            
            conn.commit()
            return web.json_response({'success': True, 'count': len(item_ids)})
        finally:
            conn.close()
    
    async def handle_api_auto_tag(self, request):
        """API: Automatisches Tagging"""
        data = await request.json()
        item_id = data.get('item_id')
        
        if not item_id:
            return web.json_response({'error': 'item_id required'}, status=400)
        
        conn = self.get_db_connection()
        try:
            await self.auto_tag_item(conn, item_id)
            return web.json_response({'success': True})
        finally:
            conn.close()
    
    async def auto_tag_item(self, conn: sqlite3.Connection, item_id: int):
        """Automatisches Tagging für einen Eintrag"""
        item = self.get_item(conn, item_id)
        if not item:
            return
        
        new_tags = []
        
        if item.type == 'file':
            file_path = Path(item.path)
            
            # Dateityp-Tag
            file_type = self.get_file_type(file_path)
            new_tags.append(file_type)
            
            # Erweiterung als Tag
            if file_path.suffix:
                ext_tag = file_path.suffix[1:].lower()  # Ohne Punkt
                new_tags.append(ext_tag)
            
            # Größen-Kategorie
            if item.file_size:
                size_mb = item.file_size / (1024 * 1024)
                if size_mb < 1:
                    new_tags.append('size_small')
                elif size_mb < 10:
                    new_tags.append('size_medium')
                elif size_mb < 100:
                    new_tags.append('size_large')
                else:
                    new_tags.append('size_xlarge')
            
            # Video-Dauer
            if item.duration:
                if item.duration < 60:
                    new_tags.append('duration_short')
                elif item.duration < 300:
                    new_tags.append('duration_medium')
                elif item.duration < 1800:
                    new_tags.append('duration_long')
                else:
                    new_tags.append('duration_xlong')
            
            # Verzeichnis-Tags
            parent_dirs = list(file_path.parent.parts[-3:])  # Letzte 3 Verzeichnisse
            for dir_name in parent_dirs:
                if dir_name and dir_name not in ('.', '..'):
                    new_tags.append(f"dir_{dir_name.lower()}")
        
        elif item.type == 'url':
            try:
                parsed = urlparse(item.path)
                # Domain als Tag
                domain = parsed.netloc
                if domain:
                    # Entferne www.
                    if domain.startswith('www.'):
                        domain = domain[4:]
                    new_tags.append(f"site_{domain.split('.')[0]}")
                
                # Protocol als Tag
                new_tags.append(f"proto_{parsed.scheme}")
                
                # YouTube-spezifisch
                if 'youtube.com' in item.path or 'youtu.be' in item.path:
                    new_tags.extend(['youtube', 'video'])
                
                # Bild-URLs erkennen
                if any(ext in item.path.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                    new_tags.append('image')
                
            except Exception:
                pass
        
        # Entferne Duplikate und leere Tags
        new_tags = list(set([t for t in new_tags if t]))
        
        # Füge neue Tags hinzu
        if new_tags:
            now = datetime.now().isoformat()
            for tag_name in new_tags:
                tag_id = self._get_or_create_tag(conn, tag_name)
                conn.execute('''
                    INSERT OR IGNORE INTO item_tags (item_id, tag_id, added_at)
                    VALUES (?, ?, ?)
                ''', (item_id, tag_id, now))
            
            conn.commit()
            self.logger.info(f"Auto-tagged item {item_id}: {new_tags}")
    
    async def handle_api_lists(self, request):
        """API: Holt alle Listen"""
        conn = self.get_db_connection()
        try:
            cur = conn.execute('SELECT id, name, description, is_encrypted, created_at FROM custom_lists ORDER BY name')
            lists = [dict(row) for row in cur.fetchall()]
            return web.json_response({'lists': lists})
        finally:
            conn.close()
    
    async def handle_api_stats(self, request):
        """API: Statistiken"""
        conn = self.get_db_connection()
        try:
            cur = conn.execute('SELECT type, COUNT(*) as count FROM items GROUP BY type')
            type_stats = {row['type']: row['count'] for row in cur.fetchall()}
            
            cur = conn.execute('SELECT COUNT(*) as count FROM tags')
            tag_count = cur.fetchone()['count']
            
            cur = conn.execute('SELECT COUNT(*) as count FROM custom_lists')
            list_count = cur.fetchone()['count']
            
            return web.json_response({
                'stats': {
                    'total_items': sum(type_stats.values()),
                    'files': type_stats.get('file', 0),
                    'urls': type_stats.get('url', 0),
                    'tags': tag_count,
                    'lists': list_count,
                    'server_uptime': time.time() - self.start_time
                }
            })
        finally:
            conn.close()
    
    async def handle_api_upload(self, request):
        """API: Datei-Upload"""
        try:
            reader = await request.multipart()
            
            while True:
                field = await reader.next()
                if not field:
                    break
                    
                if field.name == 'file':
                    filename = field.filename
                    size = 0
                    
                    # Speichere die Datei
                    upload_dir = DB_DIR / 'uploads'
                    upload_dir.mkdir(exist_ok=True)
                    
                    file_path = upload_dir / filename
                    
                    with open(file_path, 'wb') as f:
                        while True:
                            chunk = await field.read_chunk()
                            if not chunk:
                                break
                            size += len(chunk)
                            f.write(chunk)
                    
                    # Füge zur Datenbank hinzu
                    conn = self.get_db_connection()
                    try:
                        item_id = self.add_item(conn, {
                            'path': str(file_path),
                            'title': filename,
                            'type': 'file'
                        })
                        
                        item = self.get_item(conn, item_id)
                        return web.json_response({
                            'success': True,
                            'item': self.item_to_dict(item)
                        })
                    finally:
                        conn.close()
            
            return web.json_response({'error': 'No file uploaded'}, status=400)
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    # ==================== Admin API ====================
    
    async def handle_api_restart(self, request):
        """API: Server neustarten"""
        self.logger.info("Restart requested")
        return web.json_response({'status': 'restarting'})
    
    async def handle_api_shutdown(self, request):
        """API: Server herunterfahren"""
        self.logger.info("Shutdown requested")
        asyncio.create_task(self.graceful_shutdown())
        return web.json_response({'status': 'shutting_down'})
    
    async def graceful_shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Initiating graceful shutdown...")
        self.is_running = False
        
        # Stop Watch-Thread
        self.stop_watch()
        
        await asyncio.sleep(1)
        
        if self.site:
            try:
                await self.site.stop()
            except Exception as e:
                self.logger.warning(f"Error stopping site: {e}")
        
        if self.runner:
            try:
                await self.runner.cleanup()
            except Exception as e:
                self.logger.warning(f"Error cleaning up runner: {e}")
        
        self.logger.info("Server shutdown complete")
    
    # ==================== Template Rendering ====================
    
    async def render_template(self, template_name: str, context: Dict = None) -> str:
        """Rendert HTML Templates"""
        if context is None:
            context = {}
        
        templates = {
            'index.html': self._render_index,
            'browse.html': self._render_browse,
            'search.html': self._render_search,
            'media.html': self._render_media,
            'url_view.html': self._render_url_view,
        }
        
        if template_name in templates:
            return await templates[template_name](context)
        else:
            return f"<h1>Template {template_name} nicht gefunden</h1>"
    
    async def _render_index(self, context: Dict) -> str:
        """Rendert die Hauptseite"""
        return """
        <!DOCTYPE html>
        <html lang="de">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Pandora - Media & Link Management</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: #0f0f0f; color: #f0f0f0;
                }
                .navbar {
                    background: linear-gradient(90deg, #1a1a2e 0%, #16213e 100%);
                    padding: 1rem 2rem;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                    position: fixed;
                    width: 100%;
                    top: 0;
                    z-index: 1000;
                }
                .logo {
                    font-size: 1.8rem;
                    font-weight: bold;
                    background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                }
                .nav-links {
                    display: flex;
                    gap: 1.5rem;
                }
                .nav-links a {
                    color: #f0f0f0;
                    text-decoration: none;
                    padding: 0.5rem 1rem;
                    border-radius: 4px;
                    transition: all 0.3s ease;
                }
                .nav-links a:hover {
                    background: rgba(255,255,255,0.1);
                    transform: translateY(-2px);
                }
                .hero {
                    height: 70vh;
                    background: linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.7)),
                                url('https://images.unsplash.com/photo-1519681393784-d120267933ba?ixlib=rb-4.0.3&auto=format&fit=crop&w=2070&q=80');
                    background-size: cover;
                    background-position: center;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    text-align: center;
                    padding: 0 2rem;
                    margin-top: 70px;
                }
                .hero-content {
                    max-width: 800px;
                }
                .hero h1 {
                    font-size: 3.5rem;
                    margin-bottom: 1rem;
                    background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                }
                .hero p {
                    font-size: 1.2rem;
                    margin-bottom: 2rem;
                    opacity: 0.9;
                    line-height: 1.6;
                }
                .btn {
                    display: inline-block;
                    padding: 0.8rem 2rem;
                    background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
                    color: white;
                    text-decoration: none;
                    border-radius: 30px;
                    font-weight: bold;
                    transition: all 0.3s ease;
                    border: none;
                    cursor: pointer;
                    margin: 0.5rem;
                }
                .btn:hover {
                    transform: translateY(-3px);
                    box-shadow: 0 5px 15px rgba(0,0,0,0.3);
                }
                .features {
                    padding: 4rem 2rem;
                    max-width: 1200px;
                    margin: 0 auto;
                }
                .features h2 {
                    text-align: center;
                    font-size: 2.5rem;
                    margin-bottom: 3rem;
                    color: #4ecdc4;
                }
                .feature-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 2rem;
                }
                .feature-card {
                    background: #1a1a2e;
                    padding: 2rem;
                    border-radius: 10px;
                    transition: transform 0.3s ease;
                }
                .feature-card:hover {
                    transform: translateY(-5px);
                }
                .feature-card h3 {
                    color: #ff6b6b;
                    margin-bottom: 1rem;
                }
                .quick-actions {
                    background: #16213e;
                    padding: 3rem 2rem;
                    text-align: center;
                }
                .action-buttons {
                    display: flex;
                    justify-content: center;
                    gap: 1rem;
                    flex-wrap: wrap;
                    margin-top: 2rem;
                }
                footer {
                    background: #0c0c14;
                    padding: 2rem;
                    text-align: center;
                    margin-top: 3rem;
                }
                @media (max-width: 768px) {
                    .hero h1 { font-size: 2.5rem; }
                    .nav-links { display: none; }
                    .features { padding: 2rem 1rem; }
                }
            </style>
        </head>
        <body>
            <nav class="navbar">
                <div class="logo">PANDORA</div>
                <div class="nav-links">
                    <a href="/">Home</a>
                    <a href="/browse">Browse</a>
                    <a href="/search">Search</a>
                    <a href="#" onclick="showAddDialog()">Add Item</a>
                    <a href="#" onclick="showSettings()">Settings</a>
                </div>
            </nav>

            <section class="hero">
                <div class="hero-content">
                    <h1>Your Personal Media & Link Universe</h1>
                    <p>Organize, tag, and access your files, videos, images, and URLs in one beautiful interface.
                    Stream content, manage collections, and discover new ways to organize your digital life.</p>
                    <div>
                        <a href="/browse" class="btn">Start Browsing</a>
                        <a href="#" onclick="showAddDialog()" class="btn" style="background: linear-gradient(45deg, #6b48ff, #4ecdc4);">Add Content</a>
                    </div>
                </div>
            </section>

            <section class="features">
                <h2>Everything You Need</h2>
                <div class="feature-grid">
                    <div class="feature-card">
                        <h3>📁 File Management</h3>
                        <p>Organize local files with advanced tagging, automatic categorization, and smart search.</p>
                    </div>
                    <div class="feature-card">
                        <h3>🔗 URL Collection</h3>
                        <p>Save and categorize web links, YouTube videos, and online resources with automatic metadata extraction.</p>
                    </div>
                    <div class="feature-card">
                        <h3>🏷️ Smart Tagging</h3>
                        <p>Automatic tagging based on content type, file properties, and AI-powered analysis.</p>
                    </div>
                    <div class="feature-card">
                        <h3>🎬 Media Streaming</h3>
                        <p>Stream videos and view images directly in your browser with a beautiful player.</p>
                    </div>
                    <div class="feature-card">
                        <h3>📊 Custom Lists</h3>
                        <p>Create personalized collections, favorites, and encrypted lists for private content.</p>
                    </div>
                    <div class="feature-card">
                        <h3>🔍 Advanced Search</h3>
                        <p>Find anything instantly with powerful search across all content and metadata.</p>
                    </div>
                </div>
            </section>

            <section class="quick-actions">
                <h2 style="color: #ff6b6b;">Quick Actions</h2>
                <div class="action-buttons">
                    <button class="btn" onclick="showAddDialog('file')">Add Files</button>
                    <button class="btn" onclick="showAddDialog('folder')">Add Folder</button>
                    <button class="btn" onclick="showAddDialog('url')">Add URL</button>
                    <button class="btn" onclick="window.location.href='/search'">Search</button>
                    <button class="btn" onclick="window.location.href='/browse?type=url'">View URLs</button>
                </div>
            </section>

            <footer>
                <p>Pandora Media & Link Management System</p>
                <p>Self-hosted • Privacy-focused • Open Source</p>
            </footer>

            <script>
                function showAddDialog(type = null) {
                    const modal = document.createElement('div');
                    modal.style.cssText = `
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        background: rgba(0,0,0,0.8);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        z-index: 2000;
                    `;
                    
                    let content = '';
                    if (type === 'file' || !type) {
                        content = `
                            <div style="background: #1a1a2e; padding: 2rem; border-radius: 10px; max-width: 500px; width: 90%;">
                                <h2 style="color: #4ecdc4; margin-bottom: 1rem;">Add Files</h2>
                                <input type="file" id="fileInput" multiple style="margin-bottom: 1rem; width: 100%;">
                                <div style="display: flex; gap: 1rem; justify-content: flex-end;">
                                    <button onclick="uploadFiles()" class="btn" style="padding: 0.5rem 1.5rem;">Upload</button>
                                    <button onclick="this.parentElement.parentElement.parentElement.remove()" 
                                            style="background: #555; color: white; border: none; padding: 0.5rem 1.5rem; border-radius: 4px; cursor: pointer;">
                                        Cancel
                                    </button>
                                </div>
                            </div>
                        `;
                    } else if (type === 'url') {
                        content = `
                            <div style="background: #1a1a2e; padding: 2rem; border-radius: 10px; max-width: 500px; width: 90%;">
                                <h2 style="color: #4ecdc4; margin-bottom: 1rem;">Add URL</h2>
                                <input type="text" id="urlInput" placeholder="https://example.com" 
                                       style="width: 100%; padding: 0.5rem; margin-bottom: 1rem; background: #0f0f0f; color: white; border: 1px solid #333;">
                                <input type="text" id="urlTitle" placeholder="Title (optional)" 
                                       style="width: 100%; padding: 0.5rem; margin-bottom: 1rem; background: #0f0f0f; color: white; border: 1px solid #333;">
                                <div style="display: flex; gap: 1rem; justify-content: flex-end;">
                                    <button onclick="addUrl()" class="btn" style="padding: 0.5rem 1.5rem;">Add URL</button>
                                    <button onclick="this.parentElement.parentElement.parentElement.remove()" 
                                            style="background: #555; color: white; border: none; padding: 0.5rem 1.5rem; border-radius: 4px; cursor: pointer;">
                                        Cancel
                                    </button>
                                </div>
                            </div>
                        `;
                    }
                    
                    modal.innerHTML = content;
                    document.body.appendChild(modal);
                }
                
                async function uploadFiles() {
                    const fileInput = document.getElementById('fileInput');
                    const files = fileInput.files;
                    
                    if (!files.length) {
                        alert('Please select files');
                        return;
                    }
                    
                    const formData = new FormData();
                    for (let i = 0; i < files.length; i++) {
                        formData.append('file', files[i]);
                    }
                    
                    try {
                        const response = await fetch('/api/upload', {
                            method: 'POST',
                            body: formData
                        });
                        
                        const result = await response.json();
                        if (result.success) {
                            alert(`Added ${files.length} file(s) successfully!`);
                            document.querySelector('div[style*="position: fixed; top: 0"]').remove();
                            // Refresh page or update UI
                            window.location.reload();
                        } else {
                            alert('Error: ' + (result.error || 'Unknown error'));
                        }
                    } catch (error) {
                        alert('Upload failed: ' + error.message);
                    }
                }
                
                async function addUrl() {
                    const urlInput = document.getElementById('urlInput');
                    const titleInput = document.getElementById('urlTitle');
                    
                    if (!urlInput.value) {
                        alert('Please enter a URL');
                        return;
                    }
                    
                    try {
                        const response = await fetch('/api/items', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                                path: urlInput.value,
                                title: titleInput.value || urlInput.value,
                                type: 'url'
                            })
                        });
                        
                        const result = await response.json();
                        if (result.success) {
                            alert('URL added successfully!');
                            document.querySelector('div[style*="position: fixed; top: 0"]').remove();
                            window.location.reload();
                        } else {
                            alert('Error: ' + (result.error || 'Unknown error'));
                        }
                    } catch (error) {
                        alert('Failed to add URL: ' + error.message);
                    }
                }
                
                function showSettings() {
                    alert('Settings will be available in the full version!');
                }
            </script>
        </body>
        </html>
        """
    
    async def _render_browse(self, context: Dict) -> str:
        """Rendert die Browse-Seite"""
        return """
        <!DOCTYPE html>
        <html lang="de">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Browse - Pandora</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: #0f0f0f; color: #f0f0f0;
                    padding-top: 80px;
                }
                .navbar {
                    background: #1a1a2e;
                    padding: 1rem 2rem;
                    position: fixed;
                    width: 100%;
                    top: 0;
                    z-index: 1000;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    border-bottom: 1px solid #333;
                }
                .logo {
                    font-size: 1.5rem;
                    font-weight: bold;
                    color: #4ecdc4;
                }
                .nav-links {
                    display: flex;
                    gap: 1rem;
                }
                .nav-links a {
                    color: #f0f0f0;
                    text-decoration: none;
                    padding: 0.5rem 1rem;
                    border-radius: 4px;
                }
                .nav-links a:hover {
                    background: rgba(255,255,255,0.1);
                }
                .container {
                    padding: 2rem;
                    max-width: 1400px;
                    margin: 0 auto;
                }
                .filters {
                    background: #1a1a2e;
                    padding: 1.5rem;
                    border-radius: 10px;
                    margin-bottom: 2rem;
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 1rem;
                }
                .filter-group {
                    display: flex;
                    flex-direction: column;
                    gap: 0.5rem;
                }
                .filter-group label {
                    font-size: 0.9rem;
                    opacity: 0.8;
                }
                select, input {
                    background: #0f0f0f;
                    color: white;
                    border: 1px solid #333;
                    padding: 0.5rem;
                    border-radius: 4px;
                }
                .grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                    gap: 1.5rem;
                }
                .item-card {
                    background: #1a1a2e;
                    border-radius: 10px;
                    overflow: hidden;
                    transition: transform 0.3s ease, box-shadow 0.3s ease;
                    cursor: pointer;
                }
                .item-card:hover {
                    transform: translateY(-5px);
                    box-shadow: 0 10px 20px rgba(0,0,0,0.3);
                }
                .thumbnail {
                    width: 100%;
                    height: 200px;
                    background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 3rem;
                }
                .info {
                    padding: 1rem;
                }
                .title {
                    font-weight: bold;
                    margin-bottom: 0.5rem;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                .meta {
                    font-size: 0.9rem;
                    opacity: 0.7;
                    margin-bottom: 0.5rem;
                }
                .tags {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.3rem;
                    margin-top: 0.5rem;
                }
                .tag {
                    background: #4ecdc4;
                    color: #0f0f0f;
                    padding: 0.2rem 0.5rem;
                    border-radius: 3px;
                    font-size: 0.8rem;
                }
                .pagination {
                    display: flex;
                    justify-content: center;
                    gap: 0.5rem;
                    margin-top: 2rem;
                }
                .page-btn {
                    background: #1a1a2e;
                    color: white;
                    border: 1px solid #333;
                    padding: 0.5rem 1rem;
                    border-radius: 4px;
                    cursor: pointer;
                }
                .page-btn.active {
                    background: #4ecdc4;
                    color: #0f0f0f;
                }
                .loading {
                    text-align: center;
                    padding: 2rem;
                    color: #4ecdc4;
                }
                @media (max-width: 768px) {
                    .container { padding: 1rem; }
                    .grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
                }
            </style>
        </head>
        <body>
            <nav class="navbar">
                <div class="logo">PANDORA</div>
                <div class="nav-links">
                    <a href="/">Home</a>
                    <a href="/browse">Browse</a>
                    <a href="/search">Search</a>
                    <a href="#" onclick="showAddDialog()">Add</a>
                </div>
            </nav>

            <div class="container">
                <h1>Browse Content</h1>
                
                <div class="filters">
                    <div class="filter-group">
                        <label for="type-filter">Type</label>
                        <select id="type-filter">
                            <option value="">All Types</option>
                            <option value="file">Files</option>
                            <option value="url">URLs</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label for="tag-filter">Tag</label>
                        <select id="tag-filter">
                            <option value="">All Tags</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label for="sort-filter">Sort By</label>
                        <select id="sort-filter">
                            <option value="added_at_desc">Newest First</option>
                            <option value="added_at_asc">Oldest First</option>
                            <option value="title_asc">Title A-Z</option>
                            <option value="title_desc">Title Z-A</option>
                        </select>
                    </div>
                </div>

                <div id="loading" class="loading">Loading...</div>
                <div class="grid" id="grid" style="display: none;"></div>
                <div class="pagination" id="pagination"></div>
            </div>

            <script>
                let currentPage = 1;
                const perPage = 24;
                
                async function loadItems(page = 1) {
                    const typeFilter = document.getElementById('type-filter').value;
                    const tagFilter = document.getElementById('tag-filter').value;
                    const sortFilter = document.getElementById('sort-filter').value;
                    
                    const [sortBy, sortDir] = sortFilter.split('_');
                    
                    let url = `/api/items?page=${page}&per_page=${perPage}&sort_by=${sortBy}&sort_dir=${sortDir}`;
                    if (typeFilter) url += `&type=${typeFilter}`;
                    if (tagFilter) url += `&tag=${tagFilter}`;
                    
                    document.getElementById('loading').style.display = 'block';
                    document.getElementById('grid').style.display = 'none';
                    
                    try {
                        const response = await fetch(url);
                        const data = await response.json();
                        
                        displayItems(data.items);
                        setupPagination(data.pagination);
                        
                    } catch (error) {
                        console.error('Error loading items:', error);
                        document.getElementById('loading').innerHTML = 'Error loading items';
                    }
                }
                
                function displayItems(items) {
                    const grid = document.getElementById('grid');
                    
                    if (!items || items.length === 0) {
                        grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 2rem;">No items found</div>';
                    } else {
                        grid.innerHTML = items.map(item => `
                            <div class="item-card" onclick="openItem(${item.id}, '${item.type}')">
                                <div class="thumbnail">
                                    ${item.type === 'file' ? 
                                        (item.mime_type?.startsWith('video/') ? '🎬' : 
                                         item.mime_type?.startsWith('image/') ? '🖼️' : '📄') : 
                                        '🔗'}
                                </div>
                                <div class="info">
                                    <div class="title" title="${item.title}">${item.title}</div>
                                    <div class="meta">
                                        ${item.type === 'file' ? item.file_size_formatted : 'URL'}
                                        ${item.duration_formatted ? ' • ' + item.duration_formatted : ''}
                                    </div>
                                    ${item.tags && item.tags.length > 0 ? `
                                        <div class="tags">
                                            ${item.tags.slice(0, 3).map(tag => `<span class="tag">${tag}</span>`).join('')}
                                            ${item.tags.length > 3 ? '...' : ''}
                                        </div>
                                    ` : ''}
                                </div>
                            </div>
                        `).join('');
                    }
                    
                    document.getElementById('loading').style.display = 'none';
                    grid.style.display = 'grid';
                }
                
                function setupPagination(pagination) {
                    const paginationDiv = document.getElementById('pagination');
                    if (!pagination || pagination.pages <= 1) {
                        paginationDiv.innerHTML = '';
                        return;
                    }
                    
                    const { page, pages } = pagination;
                    let html = '';
                    
                    if (page > 1) {
                        html += `<button class="page-btn" onclick="changePage(${page - 1})">←</button>`;
                    }
                    
                    for (let i = 1; i <= pages; i++) {
                        if (i === 1 || i === pages || (i >= page - 2 && i <= page + 2)) {
                            html += `<button class="page-btn ${i === page ? 'active' : ''}" onclick="changePage(${i})">${i}</button>`;
                        } else if (i === page - 3 || i === page + 3) {
                            html += '<span style="padding: 0.5rem;">...</span>';
                        }
                    }
                    
                    if (page < pages) {
                        html += `<button class="page-btn" onclick="changePage(${page + 1})">→</button>`;
                    }
                    
                    paginationDiv.innerHTML = html;
                }
                
                function changePage(newPage) {
                    currentPage = newPage;
                    loadItems(newPage);
                    window.scrollTo(0, 0);
                }
                
                function openItem(itemId, itemType) {
                    if (itemType === 'file') {
                        window.location.href = `/media/${itemId}`;
                    } else if (itemType === 'url') {
                        window.location.href = `/url/${itemId}`;
                    }
                }
                
                async function loadTags() {
                    try {
                        const response = await fetch('/api/tags');
                        const data = await response.json();
                        
                        const tagSelect = document.getElementById('tag-filter');
                        data.tags.forEach(tag => {
                            const option = document.createElement('option');
                            option.value = tag.name;
                            option.textContent = tag.name;
                            tagSelect.appendChild(option);
                        });
                    } catch (error) {
                        console.error('Error loading tags:', error);
                    }
                }
                
                // Event Listeners
                document.getElementById('type-filter').addEventListener('change', () => {
                    currentPage = 1;
                    loadItems(1);
                });
                
                document.getElementById('tag-filter').addEventListener('change', () => {
                    currentPage = 1;
                    loadItems(1);
                });
                
                document.getElementById('sort-filter').addEventListener('change', () => {
                    currentPage = 1;
                    loadItems(1);
                });
                
                // Initial load
                loadTags();
                loadItems(1);
            </script>
        </body>
        </html>
        """
    
    async def _render_search(self, context: Dict) -> str:
        """Rendert die Suchseite"""
        return """
        <!DOCTYPE html>
        <html lang="de">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Search - Pandora</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: #0f0f0f; color: #f0f0f0;
                    padding-top: 80px;
                }
                .navbar {
                    background: #1a1a2e;
                    padding: 1rem 2rem;
                    position: fixed;
                    width: 100%;
                    top: 0;
                    z-index: 1000;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    border-bottom: 1px solid #333;
                }
                .logo {
                    font-size: 1.5rem;
                    font-weight: bold;
                    color: #4ecdc4;
                }
                .nav-links {
                    display: flex;
                    gap: 1rem;
                }
                .nav-links a {
                    color: #f0f0f0;
                    text-decoration: none;
                    padding: 0.5rem 1rem;
                    border-radius: 4px;
                }
                .nav-links a:hover {
                    background: rgba(255,255,255,0.1);
                }
                .container {
                    padding: 2rem;
                    max-width: 1200px;
                    margin: 0 auto;
                }
                .search-box {
                    background: #1a1a2e;
                    padding: 2rem;
                    border-radius: 10px;
                    margin-bottom: 2rem;
                }
                .search-input {
                    width: 100%;
                    padding: 1rem;
                    background: #0f0f0f;
                    color: white;
                    border: 2px solid #4ecdc4;
                    border-radius: 5px;
                    font-size: 1.1rem;
                    margin-bottom: 1rem;
                }
                .search-options {
                    display: flex;
                    gap: 1rem;
                    flex-wrap: wrap;
                    margin-bottom: 1rem;
                }
                .search-btn {
                    background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
                    color: white;
                    border: none;
                    padding: 0.8rem 2rem;
                    border-radius: 5px;
                    font-weight: bold;
                    cursor: pointer;
                    transition: transform 0.3s ease;
                }
                .search-btn:hover {
                    transform: translateY(-2px);
                }
                .results-info {
                    margin: 1rem 0;
                    opacity: 0.8;
                }
                .grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                    gap: 1.5rem;
                    margin-top: 2rem;
                }
                .item-card {
                    background: #1a1a2e;
                    border-radius: 10px;
                    overflow: hidden;
                    transition: transform 0.3s ease;
                    cursor: pointer;
                }
                .item-card:hover {
                    transform: translateY(-5px);
                }
                .thumbnail {
                    width: 100%;
                    height: 200px;
                    background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 3rem;
                }
                .info {
                    padding: 1rem;
                }
                .title {
                    font-weight: bold;
                    margin-bottom: 0.5rem;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                .meta {
                    font-size: 0.9rem;
                    opacity: 0.7;
                }
                .loading {
                    text-align: center;
                    padding: 2rem;
                    color: #4ecdc4;
                }
            </style>
        </head>
        <body>
            <nav class="navbar">
                <div class="logo">PANDORA</div>
                <div class="nav-links">
                    <a href="/">Home</a>
                    <a href="/browse">Browse</a>
                    <a href="/search">Search</a>
                    <a href="#" onclick="showAddDialog()">Add</a>
                </div>
            </nav>

            <div class="container">
                <h1>Advanced Search</h1>
                
                <div class="search-box">
                    <input type="text" class="search-input" id="search-query" 
                           placeholder="Search for files, URLs, tags, or descriptions...">
                    
                    <div class="search-options">
                        <select id="search-type">
                            <option value="">All Types</option>
                            <option value="file">Files</option>
                            <option value="url">URLs</option>
                        </select>
                        <select id="search-sort">
                            <option value="relevance">Relevance</option>
                            <option value="newest">Newest First</option>
                            <option value="oldest">Oldest First</option>
                        </select>
                    </div>
                    
                    <button class="search-btn" onclick="performSearch()">Search</button>
                </div>
                
                <div id="results-info" class="results-info"></div>
                <div id="loading" class="loading"></div>
                <div class="grid" id="grid"></div>
            </div>

            <script>
                async function performSearch() {
                    const query = document.getElementById('search-query').value;
                    const type = document.getElementById('search-type').value;
                    const sort = document.getElementById('search-sort').value;
                    
                    if (!query.trim()) {
                        alert('Please enter a search query');
                        return;
                    }
                    
                    document.getElementById('loading').innerHTML = 'Searching...';
                    document.getElementById('grid').innerHTML = '';
                    
                    let url = `/api/search?q=${encodeURIComponent(query)}`;
                    if (type) url += `&type=${type}`;
                    
                    try {
                        const response = await fetch(url);
                        const data = await response.json();
                        
                        displayResults(data.results, query);
                        
                    } catch (error) {
                        console.error('Search error:', error);
                        document.getElementById('loading').innerHTML = 'Error searching';
                    }
                }
                
                function displayResults(results, query) {
                    const grid = document.getElementById('grid');
                    const info = document.getElementById('results-info');
                    
                    if (!results || results.length === 0) {
                        info.innerHTML = `No results found for "${query}"`;
                        grid.innerHTML = '';
                        document.getElementById('loading').innerHTML = '';
                        return;
                    }
                    
                    info.innerHTML = `Found ${results.length} results for "${query}"`;
                    
                    grid.innerHTML = results.map(item => `
                        <div class="item-card" onclick="openItem(${item.id}, '${item.type}')">
                            <div class="thumbnail">
                                ${item.type === 'file' ? 
                                    (item.mime_type?.startsWith('video/') ? '🎬' : 
                                     item.mime_type?.startsWith('image/') ? '🖼️' : '📄') : 
                                    '🔗'}
                            </div>
                            <div class="info">
                                <div class="title" title="${item.title}">${item.title}</div>
                                <div class="meta">
                                    ${item.type === 'file' ? item.file_size_formatted : 'URL'}
                                    ${item.duration_formatted ? ' • ' + item.duration_formatted : ''}
                                </div>
                            </div>
                        </div>
                    `).join('');
                    
                    document.getElementById('loading').innerHTML = '';
                }
                
                function openItem(itemId, itemType) {
                    if (itemType === 'file') {
                        window.location.href = `/media/${itemId}`;
                    } else if (itemType === 'url') {
                        window.location.href = `/url/${itemId}`;
                    }
                }
                
                // Enter key for search
                document.getElementById('search-query').addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') {
                        performSearch();
                    }
                });
            </script>
        </body>
        </html>
        """
    
    async def _render_media(self, context: Dict) -> str:
        """Rendert Medien-Viewer"""
        item = context.get('item', {})
        
        return f"""
        <!DOCTYPE html>
        <html lang="de">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{item.get('title', 'Media')} - Pandora</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: #0f0f0f; color: #f0f0f0;
                }}
                .navbar {{
                    background: #1a1a2e;
                    padding: 1rem 2rem;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    border-bottom: 1px solid #333;
                }}
                .logo {{
                    font-size: 1.5rem;
                    font-weight: bold;
                    color: #4ecdc4;
                }}
                .nav-links {{
                    display: flex;
                    gap: 1rem;
                }}
                .nav-links a {{
                    color: #f0f0f0;
                    text-decoration: none;
                    padding: 0.5rem 1rem;
                    border-radius: 4px;
                }}
                .nav-links a:hover {{
                    background: rgba(255,255,255,0.1);
                }}
                .player-container {{
                    max-width: 1200px;
                    margin: 2rem auto;
                    padding: 0 2rem;
                }}
                .media-player {{
                    background: #1a1a2e;
                    border-radius: 10px;
                    overflow: hidden;
                    margin-bottom: 2rem;
                }}
                video, img {{
                    width: 100%;
                    height: auto;
                    max-height: 70vh;
                    display: block;
                }}
                .info {{
                    padding: 2rem;
                    background: #1a1a2e;
                    border-radius: 10px;
                }}
                .title {{
                    font-size: 1.8rem;
                    margin-bottom: 1rem;
                    color: #4ecdc4;
                }}
                .meta {{
                    display: flex;
                    gap: 2rem;
                    margin-bottom: 1rem;
                    opacity: 0.8;
                }}
                .tags {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.5rem;
                    margin-top: 1rem;
                }}
                .tag {{
                    background: #4ecdc4;
                    color: #0f0f0f;
                    padding: 0.3rem 0.8rem;
                    border-radius: 3px;
                    font-size: 0.9rem;
                }}
                .actions {{
                    display: flex;
                    gap: 1rem;
                    margin-top: 1.5rem;
                }}
                .btn {{
                    background: #4ecdc4;
                    color: #0f0f0f;
                    border: none;
                    padding: 0.5rem 1.5rem;
                    border-radius: 4px;
                    cursor: pointer;
                    font-weight: bold;
                }}
                @media (max-width: 768px) {{
                    .player-container {{ padding: 0 1rem; }}
                    .meta {{ flex-direction: column; gap: 0.5rem; }}
                }}
            </style>
        </head>
        <body>
            <nav class="navbar">
                <div class="logo">PANDORA</div>
                <div class="nav-links">
                    <a href="/">Home</a>
                    <a href="/browse">Browse</a>
                    <a href="/search">Search</a>
                    <a href="#" onclick="history.back()">Back</a>
                </div>
            </nav>

            <div class="player-container">
                <div class="media-player">
                    {f'<video controls><source src="/stream/{item["id"]}" type="{item["mime_type"]}"></video>' 
                     if item.get('mime_type', '').startswith('video/') else 
                     f'<img src="/stream/{item["id"]}" alt="{item["title"]}">'}
                </div>
                
                <div class="info">
                    <h1 class="title">{item.get('title', '')}</h1>
                    
                    <div class="meta">
                        <div>Type: {item.get('type', '').upper()}</div>
                        {f'<div>Size: {item.get("file_size_formatted", "")}</div>' if item.get('file_size_formatted') else ''}
                        {f'<div>Duration: {item.get("duration_formatted", "")}</div>' if item.get('duration_formatted') else ''}
                        <div>Added: {item.get('added_at', '')}</div>
                    </div>
                    
                    {f'<p>{item.get("description", "")}</p>' if item.get('description') else ''}
                    
                    {f'''
                    <div class="tags">
                        {''.join([f'<span class="tag">{tag}</span>' for tag in item.get('tags', [])])}
                    </div>
                    ''' if item.get('tags') and len(item.get('tags', [])) > 0 else ''}
                    
                    <div class="actions">
                        <button class="btn" onclick="downloadItem()">Download</button>
                        <button class="btn" onclick="editItem()">Edit</button>
                        <button class="btn" onclick="deleteItem()">Delete</button>
                    </div>
                </div>
            </div>

            <script>
                function downloadItem() {{
                    window.open('/stream/{item["id"]}', '_blank');
                }}
                
                function editItem() {{
                    alert('Edit functionality coming soon!');
                }}
                
                async function deleteItem() {{
                    if (confirm('Are you sure you want to delete this item?')) {{
                        try {{
                            const response = await fetch('/api/items/{item["id"]}', {{
                                method: 'DELETE'
                            }});
                            const data = await response.json();
                            if (data.success) {{
                                alert('Item deleted');
                                window.location.href = '/browse';
                            }}
                        }} catch (error) {{
                            alert('Error deleting item');
                        }}
                    }}
                }}
                
                // Auto-play video if it's the first time
                document.addEventListener('DOMContentLoaded', () => {{
                    const video = document.querySelector('video');
                    if (video) {{
                        video.play().catch(() => {{
                            // Autoplay prevented, show play button
                        }});
                    }}
                }});
            </script>
        </body>
        </html>
        """
    
    async def _render_url_view(self, context: Dict) -> str:
        """Rendert URL-Viewer"""
        item = context.get('item', {})
        
        return f"""
        <!DOCTYPE html>
        <html lang="de">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{item.get('title', 'URL')} - Pandora</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: #0f0f0f; color: #f0f0f0;
                }}
                .navbar {{
                    background: #1a1a2e;
                    padding: 1rem 2rem;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    border-bottom: 1px solid #333;
                }}
                .logo {{
                    font-size: 1.5rem;
                    font-weight: bold;
                    color: #4ecdc4;
                }}
                .nav-links {{
                    display: flex;
                    gap: 1rem;
                }}
                .nav-links a {{
                    color: #f0f0f0;
                    text-decoration: none;
                    padding: 0.5rem 1rem;
                    border-radius: 4px;
                }}
                .nav-links a:hover {{
                    background: rgba(255,255,255,0.1);
                }}
                .url-container {{
                    max-width: 800px;
                    margin: 2rem auto;
                    padding: 0 2rem;
                }}
                .url-card {{
                    background: #1a1a2e;
                    border-radius: 10px;
                    padding: 2rem;
                }}
                .title {{
                    font-size: 1.8rem;
                    margin-bottom: 1rem;
                    color: #4ecdc4;
                }}
                .url {{
                    background: #0f0f0f;
                    padding: 1rem;
                    border-radius: 5px;
                    margin-bottom: 1.5rem;
                    word-break: break-all;
                    border: 1px solid #333;
                }}
                .description {{
                    margin-bottom: 1.5rem;
                    line-height: 1.6;
                }}
                .meta {{
                    display: flex;
                    gap: 2rem;
                    margin-bottom: 1.5rem;
                    opacity: 0.8;
                }}
                .tags {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.5rem;
                    margin-bottom: 1.5rem;
                }}
                .tag {{
                    background: #4ecdc4;
                    color: #0f0f0f;
                    padding: 0.3rem 0.8rem;
                    border-radius: 3px;
                    font-size: 0.9rem;
                }}
                .actions {{
                    display: flex;
                    gap: 1rem;
                    margin-top: 1.5rem;
                }}
                .btn {{
                    background: #4ecdc4;
                    color: #0f0f0f;
                    border: none;
                    padding: 0.5rem 1.5rem;
                    border-radius: 4px;
                    cursor: pointer;
                    font-weight: bold;
                }}
                .btn.open {{
                    background: #ff6b6b;
                }}
                .btn.download {{
                    background: #6b48ff;
                }}
            </style>
        </head>
        <body>
            <nav class="navbar">
                <div class="logo">PANDORA</div>
                <div class="nav-links">
                    <a href="/">Home</a>
                    <a href="/browse">Browse</a>
                    <a href="/search">Search</a>
                    <a href="#" onclick="history.back()">Back</a>
                </div>
            </nav>

            <div class="url-container">
                <div class="url-card">
                    <h1 class="title">{item.get('title', 'URL')}</h1>
                    
                    <div class="url">
                        <strong>URL:</strong> {item.get('path', '')}
                    </div>
                    
                    {f'<div class="description">{item.get("description", "")}</div>' if item.get('description') else ''}
                    
                    <div class="meta">
                        <div>Type: URL</div>
                        <div>Added: {item.get('added_at', '')}</div>
                        {f'<div>Domain: {item.get("metadata", {{}}).get("domain", "")}</div>' if item.get('metadata', {{}}).get('domain') else ''}
                    </div>
                    
                    {f'''
                    <div class="tags">
                        {''.join([f'<span class="tag">{tag}</span>' for tag in item.get('tags', [])])}
                    </div>
                    ''' if item.get('tags') and len(item.get('tags', [])) > 0 else ''}
                    
                    <div class="actions">
                        <button class="btn open" onclick="openUrl()">Open URL</button>
                        <button class="btn download" onclick="downloadUrl()">Download Content</button>
                        <button class="btn" onclick="editItem()">Edit</button>
                        <button class="btn" onclick="deleteItem()">Delete</button>
                    </div>
                </div>
            </div>

            <script>
                function openUrl() {{
                    window.open('{item.get('path', '')}', '_blank');
                }}
                
                function downloadUrl() {{
                    alert('Download functionality coming soon!');
                }}
                
                function editItem() {{
                    alert('Edit functionality coming soon!');
                }}
                
                async function deleteItem() {{
                    if (confirm('Are you sure you want to delete this URL?')) {{
                        try {{
                            const response = await fetch('/api/items/{item["id"]}', {{
                                method: 'DELETE'
                            }});
                            const data = await response.json();
                            if (data.success) {{
                                alert('URL deleted');
                                window.location.href = '/browse?type=url';
                            }}
                        }} catch (error) {{
                            alert('Error deleting URL');
                        }}
                    }}
                }}
            </script>
        </body>
        </html>
        """
    
    # ==================== Server Lifecycle ====================
    
    async def start_server(self):
        """Startet den Pandora-Server"""
        self.start_time = time.time()
        self.is_running = True
        
        self.logger.info(f"Starting Pandora Server on {HOST}:{PORT}")
        self.logger.info(f"Local access: http://localhost:{PORT}")
        self.logger.info(f"Network access: http://{self.get_local_ip()}:{PORT}")
        
        # Starte Watch-Thread
        self.start_watch()
        
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, HOST, PORT)
            await self.site.start()
            
            self.logger.info("Server started successfully!")
            
            # Hauptloop
            while self.is_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Server error: {e}")
            raise
        finally:
            if self.runner:
                await self.runner.cleanup()
    
    def get_local_ip(self):
        """Ermittelt die lokale IP-Adresse"""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

def main():
    """Hauptfunktion"""
    # Erstelle benötigte Verzeichnisse
    static_dir = Path("static")
    static_dir.mkdir(exist_ok=True)
    
    # Starte den Server
    server = PandoraServer()
    
    try:
        local_ip = server.get_local_ip()
        print(f"\n🎭 Pandora Media & Link Management")
        print(f="📍 Local: http://localhost:{PORT}")
        print(f="🌐 Network: http://{local_ip}:{PORT}")
        print(f="📁 Database: {DB_PATH}")
        print(f="📊 Supports: Files, URLs, Tags, Lists, Auto-Tagging")
        print(f="⏹️  Press Ctrl+C to stop\n")
        
        asyncio.run(server.start_server())
        
    except KeyboardInterrupt:
        print("\n🛑 Stopping server...")
        asyncio.run(server.graceful_shutdown())
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()