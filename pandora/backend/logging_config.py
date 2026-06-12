import logging
import logging.handlers
import re
import os
import hashlib
from uvicorn.logging import DefaultFormatter

# Matches standard IPv4 addresses
IP_REGEX = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
HOME_DIR = os.path.expanduser("~")

def anonymize_ip(match):
    ip = match.group(0)
    # Don't hash localhost
    if ip in ("127.0.0.1", "0.0.0.0"):
        return ip
    # Hash IP so we can track same users without knowing their IP
    hashed = hashlib.sha256(ip.encode()).hexdigest()[:8]
    return f"IP-{hashed}"

class PrivacyFormatter(logging.Formatter):
    """
    A custom formatter that ensures sensitive information like IPs
    are hashed (pseudonymized) before writing to any log output.
    """
    def format(self, record):
        original_msg = super().format(record)
        
        # Pseudonymize IP addresses
        anonymized_msg = IP_REGEX.sub(anonymize_ip, original_msg)
        
        # Redact system paths to hide usernames
        if HOME_DIR and HOME_DIR in anonymized_msg:
            anonymized_msg = anonymized_msg.replace(HOME_DIR, "~")
            
        return anonymized_msg

def setup_logging(log_dir: str) -> logging.Logger:
    """
    Configures the root logger and FastAPI/Uvicorn loggers to use the
    PrivacyFormatter and write to a rotating file in the vault directory.
    """
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "pandora.log")
    
    # 10 MB per file, max 3 backups
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=3
    )
    
    console_handler = logging.StreamHandler()
    
    formatter = PrivacyFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    standard_formatter = DefaultFormatter(
        fmt='%(levelprefix)s %(name)s - %(message)s',
        use_colors=True
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(standard_formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Capture uvicorn logs to route them through our secure formatter
    for logger_name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers = []
        uvicorn_logger.addHandler(file_handler)
        uvicorn_logger.addHandler(console_handler)
        uvicorn_logger.propagate = False

    # Disable default uvicorn access logging (we will use our own middleware)
    logging.getLogger("uvicorn.access").disabled = True

    # Suppress annoying asyncio warnings about closing streams/videos early
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)

    return logging.getLogger("pandora")
