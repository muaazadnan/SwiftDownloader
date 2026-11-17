"""SQLite database management for SwiftDownloader."""
import sqlite3
import threading
import time
import shutil
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, List, Dict, Any

from app.config import DATABASE_PATH, APP_DATA_DIR

DB_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS db_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    filename TEXT NOT NULL,
    save_path TEXT NOT NULL,
    total_size INTEGER DEFAULT 0,
    downloaded_size INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    connections INTEGER DEFAULT 1,
    category TEXT DEFAULT 'Other',
    etag TEXT,
    last_modified TEXT,
    content_type TEXT,
    sha256_hash TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS download_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    download_id INTEGER NOT NULL,
    segment_index INTEGER NOT NULL,
    start_byte INTEGER NOT NULL,
    end_byte INTEGER NOT NULL,
    downloaded_bytes INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    temp_file TEXT,
    FOREIGN KEY (download_id) REFERENCES downloads(id) ON DELETE CASCADE,
    UNIQUE(download_id, segment_index)
);

CREATE TABLE IF NOT EXISTS download_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    filename TEXT NOT NULL,
    save_path TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    category TEXT DEFAULT 'Other',
    completed_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    directory TEXT NOT NULL,
    extensions TEXT
);

CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    download_id INTEGER NOT NULL UNIQUE,
    position INTEGER NOT NULL,
    added_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (download_id) REFERENCES downloads(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS scheduler (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    download_id INTEGER,
    url TEXT,
    filename TEXT,
    scheduled_time TEXT NOT NULL,
    repeat_type TEXT DEFAULT 'once',
    enabled INTEGER DEFAULT 1,
    last_run TEXT,
    FOREIGN KEY (download_id) REFERENCES downloads(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_downloads_status ON downloads(status);
CREATE INDEX IF NOT EXISTS idx_downloads_category ON downloads(category);
CREATE INDEX IF NOT EXISTS idx_segments_download ON download_segments(download_id);
CREATE INDEX IF NOT EXISTS idx_queue_position ON queue(position);
"""


class Database:
    """Thread-safe SQLite database wrapper."""

    _instance: Optional["Database"] = None
    _lock = threading.Lock()

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DATABASE_PATH
        self._local = threading.local()
        self._init_db()

    @classmethod
    def get_instance(cls, db_path: Optional[Path] = None) -> "Database":
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(db_path)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton (for testing)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.close_all()
            cls._instance = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path), timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        conn.executescript(SCHEMA_SQL)
        # Set version
        conn.execute(
            "INSERT OR REPLACE INTO db_meta (key, value) VALUES (?, ?)",
            ("version", str(DB_VERSION)),
        )
        conn.commit()

    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a single SQL statement."""
        conn = self._get_connection()
        return conn.execute(sql, params)

    def executemany(self, sql: str, params_list: list) -> sqlite3.Cursor:
        """Execute SQL for multiple parameter sets."""
        conn = self._get_connection()
        return conn.executemany(sql, params_list)

    def commit(self):
        conn = self._get_connection()
        conn.commit()

    def close_all(self):
        """Close the thread-local connection if open."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    # --- Download CRUD ---

    def add_download(self, url: str, filename: str, save_path: str,
                     total_size: int = 0, connections: int = 1,
                     category: str = "Other", status: str = "pending") -> int:
        """Add a new download record. Returns the download ID."""
        with self.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO downloads
                   (url, filename, save_path, total_size, connections, category, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (url, filename, save_path, total_size, connections, category, status),
            )
            return cursor.lastrowid

    def get_download(self, download_id: int) -> Optional[Dict[str, Any]]:
        """Get a download by ID."""
        row = self.execute(
            "SELECT * FROM downloads WHERE id = ?", (download_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_downloads_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all downloads with a given status."""
        rows = self.execute(
            "SELECT * FROM downloads WHERE status = ? ORDER BY created_at DESC",
            (status,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_downloads(self) -> List[Dict[str, Any]]:
        """Get all downloads."""
        rows = self.execute(
            "SELECT * FROM downloads ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def update_download(self, download_id: int, **kwargs) -> None:
        """Update download fields."""
        if not kwargs:
            return
        kwargs["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [download_id]
        with self.transaction() as conn:
            conn.execute(
                f"UPDATE downloads SET {set_clause} WHERE id = ?", values
            )

    def delete_download(self, download_id: int) -> None:
        """Delete a download and its segments."""
        with self.transaction() as conn:
            conn.execute("DELETE FROM download_segments WHERE download_id = ?",
                         (download_id,))
            conn.execute("DELETE FROM queue WHERE download_id = ?",
                         (download_id,))
            conn.execute("DELETE FROM downloads WHERE id = ?", (download_id,))

    def check_duplicate_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Check if a URL is already being downloaded."""
        row = self.execute(
            "SELECT * FROM downloads WHERE url = ? AND status NOT IN ('completed', 'cancelled', 'failed')",
            (url,),
        ).fetchone()
        return dict(row) if row else None

    # --- Segments ---

    def add_segments(self, download_id: int,
                     segments: List[Dict[str, Any]]) -> None:
        """Add download segments."""
        with self.transaction() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO download_segments
                   (download_id, segment_index, start_byte, end_byte, temp_file)
                   VALUES (?, ?, ?, ?, ?)""",
                [(download_id, s["index"], s["start"], s["end"], s.get("temp_file", ""))
                 for s in segments],
            )

    def get_segments(self, download_id: int) -> List[Dict[str, Any]]:
        """Get all segments for a download."""
        rows = self.execute(
            "SELECT * FROM download_segments WHERE download_id = ? ORDER BY segment_index",
            (download_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_segment(self, segment_id: int, **kwargs) -> None:
        """Update a segment."""
        if not kwargs:
            return
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [segment_id]
        with self.transaction() as conn:
            conn.execute(
                f"UPDATE download_segments SET {set_clause} WHERE id = ?", values
            )

    # --- History ---

    def add_to_history(self, url: str, filename: str, save_path: str,
                       file_size: int = 0, category: str = "Other") -> None:
        """Add a completed download to history."""
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO download_history
                   (url, filename, save_path, file_size, category)
                   VALUES (?, ?, ?, ?, ?)""",
                (url, filename, save_path, file_size, category),
            )

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get download history."""
        rows = self.execute(
            "SELECT * FROM download_history ORDER BY completed_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def clear_history(self) -> None:
        """Clear all download history."""
        with self.transaction() as conn:
            conn.execute("DELETE FROM download_history")

    # --- Queue ---

    def add_to_queue(self, download_id: int) -> None:
        """Add a download to the queue."""
        with self.transaction() as conn:
            max_pos = conn.execute(
                "SELECT COALESCE(MAX(position), 0) FROM queue"
            ).fetchone()[0]
            conn.execute(
                "INSERT OR IGNORE INTO queue (download_id, position) VALUES (?, ?)",
                (download_id, max_pos + 1),
            )

    def get_queue(self) -> List[Dict[str, Any]]:
        """Get the download queue ordered by position."""
        rows = self.execute(
            """SELECT q.*, d.url, d.filename, d.status, d.total_size
               FROM queue q JOIN downloads d ON q.download_id = d.id
               ORDER BY q.position""",
        ).fetchall()
        return [dict(r) for r in rows]

    def remove_from_queue(self, download_id: int) -> None:
        """Remove a download from the queue."""
        with self.transaction() as conn:
            conn.execute("DELETE FROM queue WHERE download_id = ?",
                         (download_id,))

    # --- Scheduler ---

    def add_scheduled(self, url: str, filename: str, scheduled_time: str,
                      repeat_type: str = "once") -> int:
        """Add a scheduled download."""
        with self.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO scheduler (url, filename, scheduled_time, repeat_type)
                   VALUES (?, ?, ?, ?)""",
                (url, filename, scheduled_time, repeat_type),
            )
            return cursor.lastrowid

    def get_scheduled(self) -> List[Dict[str, Any]]:
        """Get all scheduled downloads."""
        rows = self.execute(
            "SELECT * FROM scheduler WHERE enabled = 1 ORDER BY scheduled_time"
        ).fetchall()
        return [dict(r) for r in rows]

    def update_scheduled(self, schedule_id: int, **kwargs) -> None:
        """Update a scheduled download."""
        if not kwargs:
            return
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [schedule_id]
        with self.transaction() as conn:
            conn.execute(
                f"UPDATE scheduler SET {set_clause} WHERE id = ?", values
            )

    def delete_scheduled(self, schedule_id: int) -> None:
        with self.transaction() as conn:
            conn.execute("DELETE FROM scheduler WHERE id = ?", (schedule_id,))

    # --- Statistics ---

    def get_stats(self) -> Dict[str, int]:
        """Get download statistics."""
        conn = self._get_connection()
        stats = {}
        for status in ("pending", "downloading", "paused", "completed",
                       "failed", "cancelled", "queued"):
            count = conn.execute(
                "SELECT COUNT(*) FROM downloads WHERE status = ?", (status,)
            ).fetchone()[0]
            stats[status] = count
        stats["total"] = conn.execute(
            "SELECT COUNT(*) FROM downloads"
        ).fetchone()[0]
        return stats

    # --- Backup ---

    def backup(self, backup_path: Optional[Path] = None) -> Path:
        """Create a database backup."""
        if backup_path is None:
            ts = time.strftime("%Y%m%d_%H%M%S")
            backup_path = APP_DATA_DIR / f"backup_{ts}.db"
        shutil.copy2(str(self.db_path), str(backup_path))
        return backup_path

    # --- Search ---

    def search_downloads(self, query: str) -> List[Dict[str, Any]]:
        """Search downloads by filename or URL."""
        pattern = f"%{query}%"
        rows = self.execute(
            """SELECT * FROM downloads
               WHERE filename LIKE ? OR url LIKE ?
               ORDER BY created_at DESC""",
            (pattern, pattern),
        ).fetchall()
        return [dict(r) for r in rows]
