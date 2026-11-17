"""Tests for configuration module."""
import pytest
from app.config import (
    get_category_for_file,
    SystemInfo,
    load_settings,
    DEFAULT_SETTINGS,
)
from app.utils.formatting import (
    format_size,
    format_speed,
    format_eta,
    format_percentage,
    truncate_filename,
    sanitize_filename,
)


class TestFileCategories:
    def test_documents(self):
        assert get_category_for_file("report.pdf") == "Documents"
        assert get_category_for_file("data.xlsx") == "Documents"

    def test_videos(self):
        assert get_category_for_file("movie.mp4") == "Videos"
        assert get_category_for_file("clip.webm") == "Videos"

    def test_music(self):
        assert get_category_for_file("song.mp3") == "Music"
        assert get_category_for_file("track.flac") == "Music"

    def test_images(self):
        assert get_category_for_file("photo.jpg") == "Images"
        assert get_category_for_file("icon.png") == "Images"

    def test_software(self):
        assert get_category_for_file("setup.exe") == "Software"
        assert get_category_for_file("app.msi") == "Software"

    def test_archives(self):
        assert get_category_for_file("backup.zip") == "Archives"
        assert get_category_for_file("files.7z") == "Archives"

    def test_other(self):
        assert get_category_for_file("unknown.xyz") == "Other"
        assert get_category_for_file("noext") == "Other"


class TestSystemInfo:
    def test_get_system_summary(self):
        info = SystemInfo.get_system_summary()
        assert "os" in info
        assert "architecture" in info
        assert "processor" in info
        assert "python_version" in info

    def test_get_os_architecture(self):
        arch = SystemInfo.get_os_architecture()
        assert isinstance(arch, str)
        assert len(arch) > 0


class TestFormatting:
    def test_format_size(self):
        assert format_size(0) == "0 B"
        assert format_size(512) == "512 B"
        assert format_size(1024) == "1.0 KB"
        assert format_size(1048576) == "1.0 MB"
        assert format_size(1073741824) == "1.0 GB"

    def test_format_speed(self):
        assert format_speed(0) == "0 B/s"
        assert "KB/s" in format_speed(5120)
        assert "MB/s" in format_speed(5242880)

    def test_format_eta(self):
        assert format_eta(0) == "—"
        assert format_eta(30) == "30s"
        assert format_eta(90) == "1m 30s"
        assert format_eta(3700) == "1h 1m"

    def test_format_percentage(self):
        assert format_percentage(50.0) == "50.0%"
        assert format_percentage(99.9) == "99.9%"

    def test_truncate_filename(self):
        assert truncate_filename("short.txt") == "short.txt"
        long_name = "a" * 50 + ".zip"
        truncated = truncate_filename(long_name, max_len=20)
        assert len(truncated) <= 20
        assert truncated.endswith(".zip")

    def test_sanitize_filename(self):
        assert sanitize_filename('file<>:"/\\|?*.txt') == "file_________.txt"
        assert sanitize_filename("") == "download"
        assert sanitize_filename("a" * 300)[:255]


class TestSettings:
    def test_default_settings_structure(self):
        assert "general" in DEFAULT_SETTINGS
        assert "downloads" in DEFAULT_SETTINGS
        assert "browser" in DEFAULT_SETTINGS
        assert "clipboard" in DEFAULT_SETTINGS
        assert "advanced" in DEFAULT_SETTINGS

    def test_load_settings_returns_defaults(self):
        """When no settings file exists, should return defaults."""
        settings = load_settings()
        assert settings["general"]["theme"] in ("dark", "light")
        assert settings["downloads"]["max_simultaneous"] > 0
