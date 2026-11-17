"""Download scheduler — runs downloads at specified times."""
import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.database import Database
from app.download_engine.manager import DownloadManager

logger = logging.getLogger("SwiftDownloader.Scheduler")


class DownloadScheduler:
    """Checks for scheduled downloads and starts them at the right time."""

    def __init__(self, manager: DownloadManager, db: Optional[Database] = None):
        self.manager = manager
        self.db = db or Database.get_instance()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start the scheduler loop."""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the scheduler."""
        self._running = False

    def _run(self):
        """Main scheduler loop — checks every 30 seconds."""
        while self._running:
            try:
                self._check_scheduled()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            time.sleep(30)

    def _check_scheduled(self):
        """Check and start any due scheduled downloads."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        scheduled = self.db.get_scheduled()

        for item in scheduled:
            if item["scheduled_time"] <= now:
                try:
                    url = item.get("url")
                    filename = item.get("filename")
                    if url:
                        self.manager.add_download(
                            url=url,
                            filename=filename,
                            start_immediately=True,
                        )
                        logger.info(f"Started scheduled download: {url}")

                    # Handle repeat
                    if item["repeat_type"] == "once":
                        self.db.update_scheduled(
                            item["id"], enabled=0,
                            last_run=now,
                        )
                    elif item["repeat_type"] == "daily":
                        next_time = datetime.strptime(
                            item["scheduled_time"], "%Y-%m-%d %H:%M:%S"
                        ) + timedelta(days=1)
                        self.db.update_scheduled(
                            item["id"],
                            scheduled_time=next_time.strftime("%Y-%m-%d %H:%M:%S"),
                            last_run=now,
                        )
                    elif item["repeat_type"] == "weekly":
                        next_time = datetime.strptime(
                            item["scheduled_time"], "%Y-%m-%d %H:%M:%S"
                        ) + timedelta(weeks=1)
                        self.db.update_scheduled(
                            item["id"],
                            scheduled_time=next_time.strftime("%Y-%m-%d %H:%M:%S"),
                            last_run=now,
                        )
                except Exception as e:
                    logger.error(f"Failed to start scheduled download: {e}")

    def add_scheduled_download(self, url: str, filename: str,
                                scheduled_time: str,
                                repeat_type: str = "once") -> int:
        """Add a new scheduled download."""
        return self.db.add_scheduled(url, filename, scheduled_time, repeat_type)

    def remove_scheduled(self, schedule_id: int) -> None:
        """Remove a scheduled download."""
        self.db.delete_scheduled(schedule_id)

    def get_all_scheduled(self):
        """Get all scheduled downloads."""
        return self.db.get_scheduled()
