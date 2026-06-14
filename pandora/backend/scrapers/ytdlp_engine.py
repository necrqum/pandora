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
        'extract_flat': False,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "title": info.get('title'),
                "duration": info.get('duration'),
                "thumbnail_url": info.get('thumbnail'),
                "tags": info.get('tags', []),
                "ext": info.get('ext', 'mp4'),
                "webpage_url": info.get('webpage_url')
            }
    except Exception as e:
        logger.error(f"Failed to fetch metadata for {url}: {e}")
        return None

def download_stream(url: str, chunk_size: int = 4 * 1024 * 1024) -> Iterator[bytes]:
    """
    Downloads media to a temporary file first to ensure valid MP4 containers
    (since piped output often breaks MP4 headers), then yields chunks.
    """
    import tempfile
    import secrets
    
    # We need a temp file that survives the yt-dlp process
    # Using the project's temp dir if available, or system temp
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    # Check if we can find state (dirty but works in this single-file context)
    # Actually, let's just use standard tempfile for now but in a safe way
    
    fd, temp_path = tempfile.mkstemp(suffix=".tmp.mp4")
    os.close(fd) # Close file descriptor, yt-dlp will open it
    
    ytdlp_path = os.path.join(base_dir, "venv", "bin", "yt-dlp")
    if not os.path.exists(ytdlp_path):
        ytdlp_path = "yt-dlp"

    cmd = [
        ytdlp_path,
        "-o", temp_path,
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--quiet",
        "--no-warnings",
        "--no-playlist",
        url
    ]
    
    try:
        # 1. Download to temp file
        subprocess.run(cmd, check=True)
        
        # 2. Yield chunks from the file
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
                    # Overwrite with zeros
                    remaining = file_size
                    zeros = b'\0' * (1024 * 1024)
                    while remaining > 0:
                        f.write(zeros[:remaining])
                        remaining -= len(zeros)
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Failed to securely delete temp file {temp_path}: {e}")
                # Fallback to normal delete
                if os.path.exists(temp_path): os.remove(temp_path)
