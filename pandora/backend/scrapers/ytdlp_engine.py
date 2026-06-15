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
                "webpage_url": info.get('webpage_url'),
                "uploader": info.get('uploader') or info.get('uploader_id')
            }
    except Exception as e:
        logger.error(f"Failed to fetch metadata for {url}: {e}")
        return None
def download_stream(url: str, temp_dir: str, chunk_size: int = 4 * 1024 * 1024) -> Iterator[bytes]:
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

    # DASH merging requires a real file output to finalize moov atom
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

