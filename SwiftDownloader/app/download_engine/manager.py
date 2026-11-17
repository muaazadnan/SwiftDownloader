"""Download manager — orchestrates multiple concurrent downloads."""
import threading
import time
import logging
from typing import Optional, Callable, Dict, List, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from app.config import (
    DEFAULT_MAX_SIMULTANEOUS_DOWNLOADS,
    DEFAULT_CONNECTIONS_PER_DOWNLOAD,
    DEFAULT_SPEED_LIMIT,
    get_category_for_file,
    load_settings,
)
from app.database import Database
from app.download_engine.engine import DownloadTask, DownloadStatus, DownloadProgress

logger = logging.getLogger("SwiftDownloader.Manager")


class DownloadManager:
    """Manages all download tasks."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database.get_instance()
        self._settings = load_settings()
        self._max_simultaneous = self._settings["downloads"]["max_simultaneous"]
        self._connections_per = self._settings["downloads"]["connections_per_download"]
        self._speed_limit = self._settings["downloads"]["speed_limit"]
        self._default_dir = Path(self._settings["downloads"]["default_directory"])
        self._auto_categorize = self._settings["downloads"]["auto_categorize"]

        self._active_tasks: Dict[int, DownloadTask] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_simultaneous * 2,
            thread_name_prefix="SwiftDL",
        )
        self._lock = threading.Lock()
        self._running = True
        self._queue_thread: Optional[threading.Thread] = None

        # Callbacks for UI updates
        self.on_download_progress: Optional[Callable[[int, DownloadProgress], None]] = None
        self.on_download_complete: Optional[Callable[[int], None]] = None
        self.on_download_error: Optional[Callable[[int, str], None]] = None
        self.on_download_added: Optional[Callable[[int], None]] = None

    def start(self):
        """Start the manager and recover any interrupted downloads."""
        self._running = True
        self._recover_downloads()
        self._queue_thread = threading.Thread(
            target=self._queue_processor, daemon=True
        )
        self._queue_thread.start()

    def stop(self):
        """Stop the manager, pausing all active downloads."""
        self._running = False
        for task in list(self._active_tasks.values()):
            task.pause()
        self._executor.shutdown(wait=False)

    def _recover_downloads(self):
        """Recover downloads that were interrupted."""
        interrupted = self.db.get_downloads_by_status("downloading")
        for dl in interrupted:
            self.db.update_download(dl["id"], status="paused")
            logger.info(f"Marked interrupted download {dl['id']} as paused")

    def add_download(self, url: str, filename: Optional[str] = None,
                     save_path: Optional[str] = None,
                     connections: Optional[int] = None,
                     start_immediately: bool = True) -> int:
        """Add a new download. Returns the download ID."""
        if not url or not url.strip():
            raise ValueError("URL cannot be empty")

        url = url.strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")

        # Check for duplicates
        existing = self.db.check_duplicate_url(url)
        if existing:
            return existing["id"]

        # Determine filename
        if not filename:
            filename = DownloadTask._extract_filename(url)

        # Determine save path
        if not save_path:
            if self._auto_categorize:
                category = get_category_for_file(filename)
                save_path = str(self._default_dir / category)
            else:
                save_path = str(self._default_dir)
        Path(save_path).mkdir(parents=True, exist_ok=True)

        category = get_category_for_file(filename)
        conns = connections or self._connections_per

        download_id = self.db.add_download(
            url=url,
            filename=filename,
            save_path=save_path,
            connections=conns,
            category=category,
            status="pending",
        )

        if self.on_download_added:
            self.on_download_added(download_id)

        if start_immediately:
            self._start_download(download_id)
        else:
            self.db.add_to_queue(download_id)
            self.db.update_download(download_id, status="queued")

        return download_id

    def _start_download(self, download_id: int) -> None:
        """Start downloading a specific download."""
        with self._lock:
            if len(self._active_tasks) >= self._max_simultaneous:
                # Queue it
                self.db.add_to_queue(download_id)
                self.db.update_download(download_id, status="queued")
                return

        dl = self.db.get_download(download_id)
        if not dl:
            return

        task = DownloadTask(
            url=dl["url"],
            save_path=dl["save_path"],
            filename=dl["filename"],
            connections=dl["connections"],
            speed_limit=self._speed_limit,
            download_id=download_id,
        )

        def on_progress(progress: DownloadProgress):
            self.db.update_download(
                download_id,
                downloaded_size=progress.downloaded_bytes,
                total_size=progress.total_bytes,
                status=progress.status.value,
            )
            if self.on_download_progress:
                self.on_download_progress(download_id, progress)

        def on_complete(t: DownloadTask):
            self.db.update_download(
                download_id,
                status="completed",
                completed_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            )
            self.db.add_to_history(
                url=t.url, filename=t.filename,
                save_path=str(t.save_path),
                file_size=t.total_size,
                category=get_category_for_file(t.filename),
            )
            # Save segments state
            if t.segments:
                self.db.add_segments(download_id, t.get_serializable_segments())
            with self._lock:
                self._active_tasks.pop(download_id, None)
            if self.on_download_complete:
                self.on_download_complete(download_id)
            # Start next queued
            self._process_queue()

        def on_error(t: DownloadTask, error: str):
            self.db.update_download(
                download_id,
                status="failed",
                error_message=error,
            )
            if t.segments:
                self.db.add_segments(download_id, t.get_serializable_segments())
            with self._lock:
                self._active_tasks.pop(download_id, None)
            if self.on_download_error:
                self.on_download_error(download_id, error)
            self._process_queue()

        task.on_progress = on_progress
        task.on_complete = on_complete
        task.on_error = on_error

        with self._lock:
            self._active_tasks[download_id] = task
        self.db.update_download(download_id, status="connecting")
        self._executor.submit(task.start)

    def pause_download(self, download_id: int) -> None:
        """Pause a download."""
        with self._lock:
            task = self._active_tasks.get(download_id)
        if task:
            task.pause()
            self.db.update_download(download_id, status="paused")
            if task.segments:
                self.db.add_segments(download_id, task.get_serializable_segments())

    def resume_download(self, download_id: int) -> None:
        """Resume a paused download."""
        dl = self.db.get_download(download_id)
        if not dl or dl["status"] != "paused":
            return

        with self._lock:
            task = self._active_tasks.get(download_id)

        if task:
            task.resume()
            self.db.update_download(download_id, status="downloading")
        else:
            # Restart the download
            self._start_download(download_id)

    def cancel_download(self, download_id: int) -> None:
        """Cancel a download."""
        with self._lock:
            task = self._active_tasks.pop(download_id, None)
        if task:
            task.cancel()
        self.db.update_download(download_id, status="cancelled")
        self.db.remove_from_queue(download_id)
        self._process_queue()

    def retry_download(self, download_id: int) -> None:
        """Retry a failed download."""
        dl = self.db.get_download(download_id)
        if not dl:
            return
        self.db.update_download(
            download_id,
            status="pending",
            downloaded_size=0,
            error_message="",
            retry_count=dl["retry_count"] + 1,
        )
        self._start_download(download_id)

    def delete_download(self, download_id: int, delete_file: bool = False) -> None:
        """Delete a download record and optionally its file."""
        self.cancel_download(download_id)
        if delete_file:
            dl = self.db.get_download(download_id)
            if dl:
                file_path = Path(dl["save_path"]) / dl["filename"]
                if file_path.exists():
                    file_path.unlink()
        self.db.delete_download(download_id)

    def get_active_tasks(self) -> Dict[int, DownloadTask]:
        """Get currently active download tasks."""
        with self._lock:
            return dict(self._active_tasks)

    def get_current_speed(self) -> float:
        """Get total current download speed in bytes/sec."""
        total = 0.0
        with self._lock:
            for task in self._active_tasks.values():
                if task.is_active:
                    elapsed = time.time() - task._last_speed_update
                    if elapsed > 0 and elapsed < 2:
                        delta = task.downloaded_bytes - task._last_downloaded
                        total += delta / elapsed
        return total

    def set_speed_limit(self, limit: int) -> None:
        """Set global speed limit in bytes/sec (0 = unlimited)."""
        self._speed_limit = limit
        with self._lock:
            for task in self._active_tasks.values():
                task.speed_limit = limit

    def set_max_simultaneous(self, count: int) -> None:
        """Set maximum simultaneous downloads."""
        self._max_simultaneous = max(1, min(count, 20))

    def _process_queue(self) -> None:
        """Process queued downloads if slots are available."""
        with self._lock:
            available_slots = self._max_simultaneous - len(self._active_tasks)

        if available_slots <= 0:
            return

        queue = self.db.get_queue()
        for item in queue[:available_slots]:
            self.db.remove_from_queue(item["download_id"])
            self._start_download(item["download_id"])

    def _queue_processor(self) -> None:
        """Background thread to process the download queue."""
        while self._running:
            try:
                self._process_queue()
            except Exception as e:
                logger.error(f"Queue processor error: {e}")
            time.sleep(2)

    def update_settings(self, settings: dict) -> None:
        """Update manager settings from the settings dict."""
        dl_settings = settings.get("downloads", {})
        self._max_simultaneous = dl_settings.get(
            "max_simultaneous", self._max_simultaneous
        )
        self._connections_per = dl_settings.get(
            "connections_per_download", self._connections_per
        )
        self._speed_limit = dl_settings.get("speed_limit", self._speed_limit)
        self._default_dir = Path(dl_settings.get(
            "default_directory", str(self._default_dir)
        ))
        self._auto_categorize = dl_settings.get(
            "auto_categorize", self._auto_categorize
        )

    def import_download_list(self, file_path: str) -> int:
        """Import downloads from a text file (one URL per line). Returns count."""
        count = 0
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                url = line.strip()
                if url and url.startswith(("http://", "https://")):
                    try:
                        self.add_download(url, start_immediately=False)
                        count += 1
                    except Exception:
                        pass
        return count

    def export_download_list(self, file_path: str) -> int:
        """Export all download URLs to a text file. Returns count."""
        downloads = self.db.get_all_downloads()
        with open(file_path, "w", encoding="utf-8") as f:
            for dl in downloads:
                f.write(dl["url"] + "\n")
        return len(downloads)
