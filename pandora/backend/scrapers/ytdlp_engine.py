import yt_dlp
import os
import logging
import subprocess
from typing import Iterator, Optional, Dict, Any

logger = logging.getLogger("pandora.scrapers.ytdlp")

def fetch_metadata(url: str) -> Optional[Dict[str, Any]]:
    """
    Fetches metadata for a given URL using yt-dlp.
    """
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            uploader = info.get('uploader') or info.get('uploader_id')
            if not uploader and 'erome.com' in url:
                import requests
                import re
                try:
                    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
                    match = re.search(r'<a[^>]*id="user_name"[^>]*>([^<]+)</a>', r.text)
                    if match:
                        uploader = match.group(1).strip()
                except Exception as e:
                    logger.warning(f"Failed to scrape erome artist: {e}")

            if info.get('_type') == 'playlist':
                entries = []
                seen_urls = set()
                for idx, entry in enumerate(info.get('entries', [])):
                    if not entry: continue
                    
                    entry_url = entry.get('url')
                    if entry_url:
                        if entry_url in seen_urls: continue
                        seen_urls.add(entry_url)
                        
                    entry_uploader = entry.get('uploader') or entry.get('uploader_id') or uploader
                    playlist_idx = entry.get('playlist_index') or (idx + 1)
                    entries.append({
                        "title": entry.get('title'),
                        "duration": entry.get('duration'),
                        "thumbnail_url": entry.get('thumbnail') or info.get('thumbnail'),
                        "tags": entry.get('tags', []),
                        "ext": entry.get('ext', 'mp4'),
                        "webpage_url": info.get('webpage_url') or url,
                        "playlist_index": playlist_idx,
                        "uploader": entry_uploader
                    })
                return {
                    "is_playlist": True,
                    "title": info.get('title'),
                    "entries": entries
                }
            else:
                return {
                    "is_playlist": False,
                    "title": info.get('title'),
                    "duration": info.get('duration'),
                    "thumbnail_url": info.get('thumbnail'),
                    "tags": info.get('tags', []),
                    "ext": info.get('ext', 'mp4'),
                    "webpage_url": info.get('webpage_url') or url,
                    "uploader": uploader
                }
    except Exception as e:
        logger.error(f"Failed to fetch metadata for {url}: {e}")
        return None

def download_stream(url: str, temp_dir: str, chunk_size: int = 4 * 1024 * 1024, playlist_index: Optional[int] = None) -> Iterator[bytes]:
    """
    Downloads media to a temporary file first to ensure valid MP4 containers
    (critical for DASH merging of high-res videos), then yields chunks.
    """
    import tempfile
    import secrets
    import shutil

    os.makedirs(temp_dir, exist_ok=True)
    # Create a unique temp file in our project's temp directory
    temp_path = os.path.join(temp_dir, f"dl_{secrets.token_hex(8)}.mp4")

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    ytdlp_path = os.path.join(base_dir, "venv", "bin", "yt-dlp")

    if not os.path.exists(ytdlp_path):
        ytdlp_path = "yt-dlp"

    cmd = [
        ytdlp_path,
        "-o", temp_path,
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--quiet",
        "--no-warnings"
    ]
    if playlist_index is not None:
        cmd.extend(["--playlist-items", str(playlist_index)])
    else:
        cmd.append("--no-playlist")
        
    cmd.append(url)

    try:
        # 1. Download/Merge to physical temp file
        subprocess.run(cmd, check=True)

        # 2. Yield chunks from the finalized file
        if os.path.exists(temp_path):
            with open(temp_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

    except Exception as e:
        logger.error(f"Download/Streaming error for {url}: {e}")
        raise
    finally:
        # 3. Secure Cleanup (Zero-fill and delete)
        if os.path.exists(temp_path):
            try:
                file_size = os.path.getsize(temp_path)
                with open(temp_path, "wb") as f:
                    remaining = file_size
                    zeros = b'\0' * (1024 * 1024)
                    while remaining > 0:
                        f.write(zeros[:remaining])
                        remaining -= len(zeros)
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Failed to securely delete temp file {temp_path}: {e}")
                if os.path.exists(temp_path): os.remove(temp_path)

