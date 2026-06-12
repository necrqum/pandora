import base64
import os
import io
from PIL import Image
import logging
import subprocess

logger = logging.getLogger("pandora.thumbnails")

from datetime import datetime

def get_file_creation_date(filepath: str) -> datetime | None:
    try:
        # On Linux, st_ctime is change time, not creation time.
        # But for media, it's often the best we have besides ffmpeg metadata.
        # Let's try to get the earliest of mtime and ctime.
        stat = os.stat(filepath)
        ts = min(stat.st_mtime, stat.st_ctime)
        return datetime.fromtimestamp(ts)
    except Exception as e:
        logger.error(f"Failed to get creation date for {filepath}: {e}")
    return None

def get_video_duration(filepath: str) -> int | None:
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", filepath
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            val = result.stdout.strip()
            if val and val != 'N/A':
                return int(float(val))
    except Exception as e:
        logger.error(f"Failed to get duration for {filepath}: {e}")
    return None

def generate_thumbnail_from_file(filepath: str, filename: str, max_size=(600, 600)) -> tuple[str | None, int | None]:
    duration = None
    try:
        ext = filename.lower().split('.')[-1]
        
        # Image processing
        if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            with Image.open(filepath) as img:
                img.thumbnail(max_size)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                out = io.BytesIO()
                img.save(out, format='JPEG', quality=70)
                b64 = base64.b64encode(out.getvalue()).decode('utf-8')
                return f"data:image/jpeg;base64,{b64}", None
                
        # Video processing using ffmpeg
        elif ext in ['mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv']:
            duration = get_video_duration(filepath)
            out_path = filepath + "_thumb.jpg"
            try:
                cmd = [
                    "ffmpeg", "-y", 
                    "-i", filepath, 
                    "-ss", "00:00:01", 
                    "-vframes", "1", 
                    "-vf", f"scale='min({max_size[0]},iw)':'min({max_size[1]},ih)':force_original_aspect_ratio=decrease",
                    "-q:v", "5", 
                    out_path
                ]
                
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                if result.returncode != 0 or not os.path.exists(out_path):
                    # Fallback to 0 seconds if the video is extremely short
                    cmd[5] = "00:00:00"
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    
                if os.path.exists(out_path):
                    with open(out_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode('utf-8')
                        return f"data:image/jpeg;base64,{b64}", duration
                else:
                    logger.warning(f"ffmpeg failed: {result.stderr}")
                    return None, duration
            finally:
                if os.path.exists(out_path):
                    os.remove(out_path)
                    
    except Exception as e:
        logger.error(f"Thumbnail generation failed for {filename}: {e}")
        return None, duration
        
    return None, None
