"""Tests for the download engine."""
import os
import time
import threading
import http.server
import tempfile
import hashlib
import pytest
from pathlib import Path

from app.download_engine.engine import DownloadTask, DownloadStatus, DownloadProgress
from app.config import TEMP_DIR


# --- Test HTTP Server ---

class TestHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that serves test files and supports range requests."""

    # Class-level test data
    test_data = b"A" * 1024 * 100  # 100 KB test file

    def log_message(self, format, *args):
        pass  # Suppress output

    def do_HEAD(self):
        if self.path == "/file.bin":
            self.send_response(200)
            self.send_header("Content-Length", str(len(self.test_data)))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("ETag", '"test-etag-123"')
            self.end_headers()
        elif self.path == "/norange.bin":
            self.send_response(200)
            self.send_header("Content-Length", str(len(self.test_data)))
            self.send_header("Content-Type", "application/octet-stream")
            self.end_headers()
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/file.bin")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/file.bin":
            range_header = self.headers.get("Range")
            if range_header:
                # Parse range
                range_spec = range_header.replace("bytes=", "")
                start, end = range_spec.split("-")
                start = int(start)
                end = int(end) if end else len(self.test_data) - 1
                chunk = self.test_data[start:end + 1]

                self.send_response(206)
                self.send_header("Content-Range",
                                 f"bytes {start}-{end}/{len(self.test_data)}")
                self.send_header("Content-Length", str(len(chunk)))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                self.wfile.write(chunk)
            else:
                self.send_response(200)
                self.send_header("Content-Length", str(len(self.test_data)))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                self.wfile.write(self.test_data)

        elif self.path == "/norange.bin":
            self.send_response(200)
            self.send_header("Content-Length", str(len(self.test_data)))
            self.end_headers()
            self.wfile.write(self.test_data)

        elif self.path == "/slow.bin":
            self.send_response(200)
            data = b"B" * 10240
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            # Send slowly
            for i in range(0, len(data), 1024):
                self.wfile.write(data[i:i + 1024])
                time.sleep(0.05)

        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/file.bin")
            self.end_headers()

        elif self.path == "/error500":
            self.send_response(500)
            self.end_headers()

        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture(scope="module")
def test_server():
    """Start a test HTTP server."""
    server = http.server.HTTPServer(("127.0.0.1", 0), TestHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture
def download_dir(tmp_path):
    """Temporary download directory."""
    d = tmp_path / "downloads"
    d.mkdir()
    return d


class TestDownloadTaskBasic:
    def test_extract_filename(self):
        assert DownloadTask._extract_filename(
            "https://example.com/path/file.zip"
        ) == "file.zip"

    def test_extract_filename_query(self):
        name = DownloadTask._extract_filename(
            "https://example.com/path/file.zip?v=1&token=abc"
        )
        assert name.startswith("file.zip")

    def test_extract_filename_no_extension(self):
        name = DownloadTask._extract_filename("https://example.com/download")
        assert name == "download"

    def test_extract_filename_sanitize(self):
        name = DownloadTask._extract_filename(
            'https://example.com/path/my<file>.zip'
        )
        assert "<" not in name
        assert ">" not in name


class TestSingleConnectionDownload:
    def test_basic_download(self, test_server, download_dir):
        """Single-connection download should work."""
        task = DownloadTask(
            url=f"{test_server}/file.bin",
            save_path=str(download_dir),
            filename="test.bin",
            connections=1,
            download_id=1,
        )
        task.start()
        assert task.status == DownloadStatus.COMPLETED
        result = download_dir / "test.bin"
        assert result.exists()
        assert result.stat().st_size == len(TestHandler.test_data)

    def test_download_no_range(self, test_server, download_dir):
        """Download from server that doesn't support ranges."""
        task = DownloadTask(
            url=f"{test_server}/norange.bin",
            save_path=str(download_dir),
            filename="norange.bin",
            connections=4,  # Should fall back to 1
            download_id=2,
        )
        task.start()
        assert task.status == DownloadStatus.COMPLETED


class TestMultiConnectionDownload:
    def test_multi_connection(self, test_server, download_dir):
        """Multi-connection download should produce correct file."""
        task = DownloadTask(
            url=f"{test_server}/file.bin",
            save_path=str(download_dir),
            filename="multi.bin",
            connections=4,
            download_id=3,
        )
        task.start()
        assert task.status == DownloadStatus.COMPLETED
        result = download_dir / "multi.bin"
        assert result.exists()
        assert result.stat().st_size == len(TestHandler.test_data)

        # Verify content integrity
        with open(result, "rb") as f:
            content = f.read()
        assert content == TestHandler.test_data


class TestPauseResume:
    def test_cancel(self, test_server, download_dir):
        """Should be able to cancel a download."""
        task = DownloadTask(
            url=f"{test_server}/slow.bin",
            save_path=str(download_dir),
            filename="cancel.bin",
            connections=1,
            download_id=4,
        )
        # Start in background and cancel
        t = threading.Thread(target=task.start)
        t.start()
        time.sleep(0.1)
        task.cancel()
        t.join(timeout=5)
        assert task.status == DownloadStatus.CANCELLED


class TestRedirects:
    def test_redirect(self, test_server, download_dir):
        """Should follow HTTP redirects."""
        task = DownloadTask(
            url=f"{test_server}/redirect",
            save_path=str(download_dir),
            filename="redirect.bin",
            connections=1,
            download_id=5,
        )
        task.start()
        assert task.status == DownloadStatus.COMPLETED


class TestErrors:
    def test_404(self, test_server, download_dir):
        """Should fail gracefully on 404."""
        task = DownloadTask(
            url=f"{test_server}/nonexistent",
            save_path=str(download_dir),
            filename="missing.bin",
            connections=1,
            download_id=6,
        )
        task.start()
        assert task.status == DownloadStatus.FAILED
        assert task.error_message

    def test_invalid_url(self, download_dir):
        """Should fail on invalid URL."""
        task = DownloadTask(
            url="not-a-url",
            save_path=str(download_dir),
            filename="bad.bin",
            connections=1,
            download_id=7,
        )
        task.start()
        assert task.status == DownloadStatus.FAILED


class TestHashVerification:
    def test_correct_hash(self, test_server, download_dir):
        """Should pass with correct SHA-256 hash."""
        expected = hashlib.sha256(TestHandler.test_data).hexdigest()
        task = DownloadTask(
            url=f"{test_server}/file.bin",
            save_path=str(download_dir),
            filename="hashed.bin",
            connections=1,
            download_id=8,
            expected_hash=expected,
        )
        task.start()
        assert task.status == DownloadStatus.COMPLETED

    def test_wrong_hash(self, test_server, download_dir):
        """Should fail with wrong SHA-256 hash."""
        task = DownloadTask(
            url=f"{test_server}/file.bin",
            save_path=str(download_dir),
            filename="badhash.bin",
            connections=1,
            download_id=9,
            expected_hash="0000000000000000000000000000000000000000000000000000000000000000",
        )
        task.start()
        assert task.status == DownloadStatus.FAILED
        assert "hash" in task.error_message.lower()


class TestProgress:
    def test_progress_callback(self, test_server, download_dir):
        """Progress callback should fire during download."""
        progress_updates = []

        def on_progress(p: DownloadProgress):
            progress_updates.append(p)

        task = DownloadTask(
            url=f"{test_server}/file.bin",
            save_path=str(download_dir),
            filename="progress.bin",
            connections=1,
            download_id=10,
        )
        task.on_progress = on_progress
        task.start()

        assert len(progress_updates) > 0
        assert any(p.status == DownloadStatus.COMPLETED for p in progress_updates)
