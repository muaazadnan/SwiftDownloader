"""Core download engine with multi-connection support."""
import os
import time
import hashlib
import threading
import tempfile
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, Dict, List, Any
from dataclasses import dataclass, field
from urllib.parse import urlparse, unquote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CONNECTIONS_PER_DOWNLOAD,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_DELAY_SECONDS,
    MIN_SEGMENT_SIZE,
    TEMP_DIR,
)


class DownloadStatus(Enum):
    PENDING = "pending"
    CONNECTING = "connecting"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    MERGING = "merging"
    VERIFYING = "verifying"
    QUEUED = "queued"


@dataclass
class DownloadProgress:
    """Tracks download progress."""
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0  # bytes/sec
    eta: float = 0.0  # seconds
    percentage: float = 0.0
    status: DownloadStatus = DownloadStatus.PENDING
    active_connections: int = 0
    error_message: str = ""


@dataclass
class SegmentInfo:
    """Information about a download segment."""
    index: int
    start_byte: int
    end_byte: int
    downloaded_bytes: int = 0
    temp_file: str = ""
    status: str = "pending"


class DownloadTask:
    """Represents a single download task."""

    def __init__(self, url: str, save_path: str, filename: Optional[str] = None,
                 connections: int = DEFAULT_CONNECTIONS_PER_DOWNLOAD,
                 speed_limit: int = 0,
                 timeout: int = DEFAULT_TIMEOUT_SECONDS,
                 retry_count: int = DEFAULT_RETRY_COUNT,
                 expected_hash: Optional[str] = None,
                 download_id: Optional[int] = None):
        self.url = url
        self.save_path = Path(save_path)
        self.filename = filename or self._extract_filename(url)
        self.connections = connections
        self.speed_limit = speed_limit  # bytes/sec, 0=unlimited
        self.timeout = timeout
        self.retry_count = retry_count
        self.expected_hash = expected_hash
        self.download_id = download_id

        self.total_size: int = 0
        self.downloaded_bytes: int = 0
        self.status = DownloadStatus.PENDING
        self.error_message: str = ""
        self.etag: Optional[str] = None
        self.last_modified: Optional[str] = None
        self.content_type: Optional[str] = None
        self.supports_range: bool = False
        self.segments: List[SegmentInfo] = []
        self.segment_threads: List[threading.Thread] = []

        self._lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially

        self._speed_samples: List[tuple] = []
        self._last_speed_update = time.time()
        self._last_downloaded = 0

        # Callbacks
        self.on_progress: Optional[Callable[[DownloadProgress], None]] = None
        self.on_complete: Optional[Callable[["DownloadTask"], None]] = None
        self.on_error: Optional[Callable[["DownloadTask", str], None]] = None

    @staticmethod
    def _extract_filename(url: str) -> str:
        """Extract filename from URL."""
        parsed = urlparse(url)
        path = unquote(parsed.path)
        name = os.path.basename(path)
        if not name or "." not in name:
            name = "download"
        # Sanitize
        invalid_chars = '<>:"/\\|?*'
        for c in invalid_chars:
            name = name.replace(c, "_")
        return name[:255]

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic."""
        session = requests.Session()
        retry_strategy = Retry(
            total=self.retry_count,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({
            "User-Agent": "SwiftDownloader/1.0",
            "Accept": "*/*",
            "Accept-Encoding": "identity",
        })
        return session

    def _probe_url(self, session: requests.Session) -> None:
        """Probe URL for file info and range support."""
        self.status = DownloadStatus.CONNECTING
        self._emit_progress()

        response = session.head(self.url, timeout=self.timeout,
                                allow_redirects=True)
        response.raise_for_status()

        self.total_size = int(response.headers.get("Content-Length", 0))
        self.etag = response.headers.get("ETag")
        self.last_modified = response.headers.get("Last-Modified")
        self.content_type = response.headers.get("Content-Type", "")

        accept_ranges = response.headers.get("Accept-Ranges", "")
        if accept_ranges.lower() == "bytes" and self.total_size > 0:
            self.supports_range = True
        elif self.total_size > 0:
            # Try a range request to verify
            try:
                test = session.head(
                    self.url, timeout=self.timeout,
                    headers={"Range": "bytes=0-0"},
                    allow_redirects=True,
                )
                self.supports_range = test.status_code == 206
            except Exception:
                self.supports_range = False

    def _plan_segments(self) -> None:
        """Plan download segments based on file size and connection count."""
        if not self.supports_range or self.total_size <= MIN_SEGMENT_SIZE:
            # Single-connection download
            self.segments = [SegmentInfo(
                index=0, start_byte=0,
                end_byte=self.total_size - 1 if self.total_size > 0 else 0,
                temp_file=str(TEMP_DIR / f"{self.download_id}_seg0.part"),
            )]
            return

        num_connections = min(
            self.connections,
            max(1, self.total_size // MIN_SEGMENT_SIZE),
        )
        segment_size = self.total_size // num_connections
        self.segments = []

        for i in range(num_connections):
            start = i * segment_size
            end = (start + segment_size - 1) if i < num_connections - 1 else (self.total_size - 1)
            self.segments.append(SegmentInfo(
                index=i, start_byte=start, end_byte=end,
                temp_file=str(TEMP_DIR / f"{self.download_id}_seg{i}.part"),
            ))

    def _download_segment(self, segment: SegmentInfo,
                          session: requests.Session) -> None:
        """Download a single segment."""
        if self._cancel_event.is_set():
            return

        segment.status = "downloading"
        headers = {}

        # Resume from where we left off
        actual_start = segment.start_byte + segment.downloaded_bytes
        if self.supports_range and self.total_size > 0:
            headers["Range"] = f"bytes={actual_start}-{segment.end_byte}"

        try:
            response = session.get(
                self.url, headers=headers, stream=True,
                timeout=self.timeout, allow_redirects=True,
            )
            if self.supports_range and self.total_size > 0:
                if response.status_code not in (200, 206):
                    raise requests.HTTPError(
                        f"Server returned {response.status_code}"
                    )
            else:
                response.raise_for_status()

            mode = "ab" if segment.downloaded_bytes > 0 else "wb"
            with open(segment.temp_file, mode) as f:
                for chunk in response.iter_content(chunk_size=DEFAULT_CHUNK_SIZE):
                    if self._cancel_event.is_set():
                        return

                    # Handle pause
                    self._pause_event.wait()

                    if chunk:
                        f.write(chunk)
                        chunk_len = len(chunk)
                        segment.downloaded_bytes += chunk_len
                        with self._lock:
                            self.downloaded_bytes += chunk_len

                        # Speed limiting
                        if self.speed_limit > 0:
                            self._apply_speed_limit(chunk_len)

                        self._emit_progress()

            segment.status = "completed"

        except requests.RequestException as e:
            segment.status = "failed"
            raise

    def _apply_speed_limit(self, chunk_len: int) -> None:
        """Apply speed limiting by sleeping if needed."""
        if self.speed_limit <= 0:
            return
        now = time.time()
        with self._lock:
            self._speed_samples.append((now, chunk_len))
            # Clean old samples (last 1 second)
            self._speed_samples = [
                (t, s) for t, s in self._speed_samples if now - t < 1.0
            ]
            total_in_window = sum(s for _, s in self._speed_samples)
            if total_in_window > self.speed_limit:
                sleep_time = (total_in_window - self.speed_limit) / self.speed_limit
                time.sleep(min(sleep_time, 1.0))

    def _merge_segments(self) -> None:
        """Merge all segment files into the final file."""
        self.status = DownloadStatus.MERGING
        self._emit_progress()

        final_path = self.save_path / self.filename
        final_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file first, then rename (atomic-ish)
        temp_final = final_path.with_suffix(final_path.suffix + ".swdltmp")

        try:
            with open(temp_final, "wb") as outfile:
                for segment in sorted(self.segments, key=lambda s: s.index):
                    seg_path = Path(segment.temp_file)
                    if seg_path.exists():
                        with open(seg_path, "rb") as infile:
                            while True:
                                chunk = infile.read(DEFAULT_CHUNK_SIZE * 16)
                                if not chunk:
                                    break
                                outfile.write(chunk)

            # Atomic rename
            if final_path.exists():
                final_path.unlink()
            temp_final.rename(final_path)

        except Exception:
            if temp_final.exists():
                temp_final.unlink()
            raise
        finally:
            # Clean up segment temp files
            for segment in self.segments:
                try:
                    seg_path = Path(segment.temp_file)
                    if seg_path.exists():
                        seg_path.unlink()
                except OSError:
                    pass

    def _verify_hash(self) -> bool:
        """Verify file hash if expected hash is provided."""
        if not self.expected_hash:
            return True

        self.status = DownloadStatus.VERIFYING
        self._emit_progress()

        final_path = self.save_path / self.filename
        sha256 = hashlib.sha256()
        with open(final_path, "rb") as f:
            while True:
                chunk = f.read(DEFAULT_CHUNK_SIZE * 16)
                if not chunk:
                    break
                sha256.update(chunk)

        return sha256.hexdigest().lower() == self.expected_hash.lower()

    def compute_file_hash(self) -> str:
        """Compute SHA-256 hash of the downloaded file."""
        final_path = self.save_path / self.filename
        if not final_path.exists():
            return ""
        sha256 = hashlib.sha256()
        with open(final_path, "rb") as f:
            while True:
                chunk = f.read(DEFAULT_CHUNK_SIZE * 16)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()

    def _emit_progress(self) -> None:
        """Emit progress update."""
        if not self.on_progress:
            return

        now = time.time()
        elapsed = now - self._last_speed_update
        if elapsed >= 0.5:  # Update speed every 0.5s
            bytes_delta = self.downloaded_bytes - self._last_downloaded
            speed = bytes_delta / elapsed if elapsed > 0 else 0
            self._last_speed_update = now
            self._last_downloaded = self.downloaded_bytes
        else:
            speed = 0

        percentage = 0.0
        eta = 0.0
        if self.total_size > 0:
            percentage = (self.downloaded_bytes / self.total_size) * 100
            if speed > 0:
                remaining = self.total_size - self.downloaded_bytes
                eta = remaining / speed

        active = sum(1 for s in self.segments if s.status == "downloading")

        progress = DownloadProgress(
            downloaded_bytes=self.downloaded_bytes,
            total_bytes=self.total_size,
            speed=speed,
            eta=eta,
            percentage=percentage,
            status=self.status,
            active_connections=active,
            error_message=self.error_message,
        )
        try:
            self.on_progress(progress)
        except Exception:
            pass

    def start(self) -> None:
        """Start the download in the current thread."""
        session = self._create_session()
        try:
            # 1. Probe URL
            self._probe_url(session)

            # 2. Plan segments
            self._plan_segments()

            # 3. Download all segments
            self.status = DownloadStatus.DOWNLOADING
            self._last_speed_update = time.time()
            self._last_downloaded = 0
            self._emit_progress()

            if len(self.segments) == 1:
                # Single-connection
                self._download_segment(self.segments[0], session)
            else:
                # Multi-connection: each segment in its own thread
                self.segment_threads = []
                errors = []

                def segment_worker(seg):
                    try:
                        seg_session = self._create_session()
                        self._download_segment(seg, seg_session)
                    except Exception as e:
                        errors.append(str(e))

                for seg in self.segments:
                    t = threading.Thread(target=segment_worker, args=(seg,),
                                         daemon=True)
                    self.segment_threads.append(t)
                    t.start()

                for t in self.segment_threads:
                    t.join()

                if errors and not self._cancel_event.is_set():
                    raise requests.RequestException(
                        f"Segment errors: {'; '.join(errors[:3])}"
                    )

            if self._cancel_event.is_set():
                self.status = DownloadStatus.CANCELLED
                self._emit_progress()
                return

            # 4. Merge segments
            self._merge_segments()

            # 5. Verify hash
            if not self._verify_hash():
                self.status = DownloadStatus.FAILED
                self.error_message = "SHA-256 hash verification failed"
                self._emit_progress()
                if self.on_error:
                    self.on_error(self, self.error_message)
                return

            # 6. Done
            self.status = DownloadStatus.COMPLETED
            self._emit_progress()
            if self.on_complete:
                self.on_complete(self)

        except Exception as e:
            if self._cancel_event.is_set():
                self.status = DownloadStatus.CANCELLED
            else:
                self.status = DownloadStatus.FAILED
                self.error_message = str(e)
            self._emit_progress()
            if self.on_error and not self._cancel_event.is_set():
                self.on_error(self, str(e))

    def pause(self) -> None:
        """Pause the download."""
        self._pause_event.clear()
        self.status = DownloadStatus.PAUSED
        self._emit_progress()

    def resume(self) -> None:
        """Resume a paused download."""
        self._pause_event.set()
        self.status = DownloadStatus.DOWNLOADING
        self._emit_progress()

    def cancel(self) -> None:
        """Cancel the download."""
        self._cancel_event.set()
        self._pause_event.set()  # Unblock if paused
        self.status = DownloadStatus.CANCELLED
        self._emit_progress()

    @property
    def is_active(self) -> bool:
        return self.status in (
            DownloadStatus.DOWNLOADING,
            DownloadStatus.CONNECTING,
            DownloadStatus.MERGING,
            DownloadStatus.VERIFYING,
        )

    def get_serializable_segments(self) -> List[Dict[str, Any]]:
        """Get segment info for database storage."""
        return [
            {
                "index": s.index,
                "start": s.start_byte,
                "end": s.end_byte,
                "downloaded_bytes": s.downloaded_bytes,
                "temp_file": s.temp_file,
                "status": s.status,
            }
            for s in self.segments
        ]
