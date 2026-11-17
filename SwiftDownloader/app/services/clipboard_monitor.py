"""Clipboard monitoring for URL detection."""
import re
import threading
import time
import logging
from typing import Optional, Callable

logger = logging.getLogger("SwiftDownloader.Clipboard")

# URL pattern for HTTP/HTTPS links that look like file downloads
URL_PATTERN = re.compile(
    r'https?://[^\s<>"\']+\.'
    r'(?:zip|rar|7z|exe|msi|dmg|iso|tar|gz|bz2|xz|'
    r'pdf|doc|docx|xls|xlsx|ppt|pptx|'
    r'mp4|mkv|avi|mov|wmv|flv|webm|'
    r'mp3|flac|aac|ogg|wav|'
    r'jpg|jpeg|png|gif|bmp|svg|webp|'
    r'apk|deb|rpm|appimage)'
    r'(?:\?[^\s<>"\']*)?',
    re.IGNORECASE,
)


class ClipboardMonitor:
    """Monitors the system clipboard for downloadable URLs."""

    def __init__(self, on_url_detected: Optional[Callable[[str], None]] = None):
        self.on_url_detected = on_url_detected
        self._running = False
        self._enabled = False
        self._thread: Optional[threading.Thread] = None
        self._last_text: str = ""
        self._clipboard_func: Optional[Callable] = None

    def start(self):
        """Start clipboard monitoring."""
        self._running = True
        self._enabled = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop clipboard monitoring."""
        self._running = False
        self._enabled = False

    def set_enabled(self, enabled: bool):
        """Enable or disable monitoring."""
        self._enabled = enabled

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def _get_clipboard_text(self) -> str:
        """Get text from system clipboard."""
        try:
            # Try PySide6 clipboard
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                clipboard = app.clipboard()
                return clipboard.text() or ""
        except ImportError:
            pass

        # Fallback: try pyperclip or win32 API
        try:
            import pyperclip
            return pyperclip.paste() or ""
        except ImportError:
            pass

        return ""

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            if self._enabled:
                try:
                    text = self._get_clipboard_text()
                    if text and text != self._last_text:
                        self._last_text = text
                        urls = URL_PATTERN.findall(text)
                        for url in urls:
                            if self.on_url_detected:
                                self.on_url_detected(url)
                except Exception as e:
                    logger.debug(f"Clipboard check error: {e}")
            time.sleep(1.5)
