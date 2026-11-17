"""Tests for the database module."""
import os
import tempfile
import pytest
from pathlib import Path

from app.database import Database


@pytest.fixture
def db(tmp_path):
    """Create a fresh test database."""
    Database.reset_instance()
    db_path = tmp_path / "test.db"
    return Database(db_path)


class TestDatabaseBasic:
    def test_create_database(self, db):
        """Database should initialize without errors."""
        assert db.db_path.exists()

    def test_add_download(self, db):
        """Should add a download and return a valid ID."""
        dl_id = db.add_download(
            url="https://example.com/file.zip",
            filename="file.zip",
            save_path="/tmp/downloads",
            total_size=1024,
            connections=4,
            category="Archives",
        )
        assert dl_id > 0

    def test_get_download(self, db):
        """Should retrieve a download by ID."""
        dl_id = db.add_download(
            url="https://example.com/file.zip",
            filename="file.zip",
            save_path="/tmp/downloads",
        )
        dl = db.get_download(dl_id)
        assert dl is not None
        assert dl["url"] == "https://example.com/file.zip"
        assert dl["filename"] == "file.zip"
        assert dl["status"] == "pending"

    def test_update_download(self, db):
        """Should update download fields."""
        dl_id = db.add_download(
            url="https://example.com/file.zip",
            filename="file.zip",
            save_path="/tmp",
        )
        db.update_download(dl_id, status="downloading", downloaded_size=512)
        dl = db.get_download(dl_id)
        assert dl["status"] == "downloading"
        assert dl["downloaded_size"] == 512

    def test_delete_download(self, db):
        """Should delete a download."""
        dl_id = db.add_download(
            url="https://example.com/file.zip",
            filename="file.zip",
            save_path="/tmp",
        )
        db.delete_download(dl_id)
        assert db.get_download(dl_id) is None

    def test_duplicate_check(self, db):
        """Should detect duplicate URLs."""
        db.add_download(
            url="https://example.com/file.zip",
            filename="file.zip",
            save_path="/tmp",
            status="downloading",
        )
        dup = db.check_duplicate_url("https://example.com/file.zip")
        assert dup is not None

    def test_no_false_duplicate(self, db):
        """Completed downloads should not trigger duplicate detection."""
        db.add_download(
            url="https://example.com/file.zip",
            filename="file.zip",
            save_path="/tmp",
            status="completed",
        )
        dup = db.check_duplicate_url("https://example.com/file.zip")
        assert dup is None


class TestDatabaseSegments:
    def test_add_and_get_segments(self, db):
        """Should store and retrieve download segments."""
        dl_id = db.add_download(
            url="https://example.com/large.zip",
            filename="large.zip",
            save_path="/tmp",
        )
        segments = [
            {"index": 0, "start": 0, "end": 999, "temp_file": "/tmp/seg0"},
            {"index": 1, "start": 1000, "end": 1999, "temp_file": "/tmp/seg1"},
        ]
        db.add_segments(dl_id, segments)
        result = db.get_segments(dl_id)
        assert len(result) == 2
        assert result[0]["start_byte"] == 0
        assert result[1]["end_byte"] == 1999


class TestDatabaseHistory:
    def test_add_and_get_history(self, db):
        """Should track download history."""
        db.add_to_history("https://example.com/a.zip", "a.zip", "/tmp", 1024)
        db.add_to_history("https://example.com/b.zip", "b.zip", "/tmp", 2048)
        history = db.get_history()
        assert len(history) == 2

    def test_clear_history(self, db):
        db.add_to_history("https://example.com/a.zip", "a.zip", "/tmp", 1024)
        db.clear_history()
        assert len(db.get_history()) == 0


class TestDatabaseQueue:
    def test_queue_ordering(self, db):
        """Queue items should maintain insertion order."""
        id1 = db.add_download(url="https://a.com/1", filename="1", save_path="/tmp")
        id2 = db.add_download(url="https://a.com/2", filename="2", save_path="/tmp")
        db.add_to_queue(id1)
        db.add_to_queue(id2)
        queue = db.get_queue()
        assert len(queue) == 2
        assert queue[0]["download_id"] == id1
        assert queue[1]["download_id"] == id2

    def test_remove_from_queue(self, db):
        id1 = db.add_download(url="https://a.com/1", filename="1", save_path="/tmp")
        db.add_to_queue(id1)
        db.remove_from_queue(id1)
        assert len(db.get_queue()) == 0


class TestDatabaseScheduler:
    def test_add_scheduled(self, db):
        sid = db.add_scheduled("https://a.com/f.zip", "f.zip",
                                "2030-01-01 00:00:00", "once")
        assert sid > 0

    def test_get_scheduled(self, db):
        db.add_scheduled("https://a.com/f.zip", "f.zip",
                          "2030-01-01 00:00:00", "daily")
        result = db.get_scheduled()
        assert len(result) == 1
        assert result[0]["repeat_type"] == "daily"


class TestDatabaseStats:
    def test_stats(self, db):
        db.add_download(url="https://a.com/1", filename="1",
                        save_path="/tmp", status="completed")
        db.add_download(url="https://a.com/2", filename="2",
                        save_path="/tmp", status="failed")
        db.add_download(url="https://a.com/3", filename="3",
                        save_path="/tmp", status="downloading")
        stats = db.get_stats()
        assert stats["completed"] == 1
        assert stats["failed"] == 1
        assert stats["downloading"] == 1
        assert stats["total"] == 3


class TestDatabaseSearch:
    def test_search_by_filename(self, db):
        db.add_download(url="https://a.com/report.pdf", filename="report.pdf",
                        save_path="/tmp")
        db.add_download(url="https://a.com/photo.jpg", filename="photo.jpg",
                        save_path="/tmp")
        results = db.search_downloads("report")
        assert len(results) == 1
        assert results[0]["filename"] == "report.pdf"

    def test_search_by_url(self, db):
        db.add_download(url="https://github.com/release.zip",
                        filename="release.zip", save_path="/tmp")
        results = db.search_downloads("github")
        assert len(results) == 1


class TestDatabaseBackup:
    def test_backup(self, db, tmp_path):
        db.add_download(url="https://a.com/1", filename="1", save_path="/tmp")
        backup_path = db.backup(tmp_path / "backup.db")
        assert backup_path.exists()
        assert backup_path.stat().st_size > 0
