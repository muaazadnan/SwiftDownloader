"""Logging setup for SwiftDownloader."""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

from app.config import LOG_PATH


def setup_logging(level: str = "INFO") -> None:
    """Configure application logging."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Root logger
    root = logging.getLogger("SwiftDownloader")
    root.setLevel(log_level)

    # Format
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler with rotation (5 MB, keep 3 backups)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(
        str(LOG_PATH), maxBytes=5 * 1024 * 1024, backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(log_level)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Console handler (for development)
    if "--debug" in sys.argv:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(fmt)
        root.addHandler(ch)
