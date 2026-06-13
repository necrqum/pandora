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
    Returns an iterator that yields chunks of the media file by piping yt-dlp stdout.
    """
    # We use the full path to yt-dlp in our venv to be safe
    # Finding the path relative to this file
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    ytdlp_path = os.path.join(base_dir, "venv", "bin", "yt-dlp")
    
    if not os.path.exists(ytdlp_path):
        # Fallback to system yt-dlp if venv one is missing
        ytdlp_path = "yt-dlp"

    cmd = [
        ytdlp_path,
        "-o", "-", # Output to stdout
        "-f", "bestvideo+bestaudio/best",
        "--quiet",
        "--no-warnings",
        "--no-playlist",
        url
    ]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=chunk_size)
        
        while True:
            chunk = process.stdout.read(chunk_size)
            if not chunk:
                break
            yield chunk
            
        process.stdout.close()
        return_code = process.wait()
        if return_code != 0:
            stderr = process.stderr.read().decode('utf-8')
            logger.error(f"yt-dlp failed with code {return_code}: {stderr}")
            
    except Exception as e:
        logger.error(f"Streaming error for {url}: {e}")
        raise
