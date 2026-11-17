"""Application configuration and constants."""
import os
import sys
import platform
import ctypes
import json
from pathlib import Path

APP_NAME = "SwiftDownloader"
APP_VERSION = "1.0.0"
APP_TAGLINE = "Free. Fast. Unlimited."
APP_AUTHOR = "SwiftDownloader Contributors"
APP_LICENSE = "MIT"

# --- Paths ---
def get_app_data_dir() -> Path:
    """Get the application data directory."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".local" / "share"
    app_dir = base / APP_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir

def get_default_download_dir() -> Path:
    """Get the default download directory."""
    if sys.platform == "win32":
        downloads = Path.home() / "Downloads" / APP_NAME
    else:
        downloads = Path.home() / "Downloads" / APP_NAME
    downloads.mkdir(parents=True, exist_ok=True)
    return downloads

def get_temp_dir() -> Path:
    """Get the temporary directory for partial downloads."""
    temp = get_app_data_dir() / "temp"
    temp.mkdir(parents=True, exist_ok=True)
    return temp

APP_DATA_DIR = get_app_data_dir()
DATABASE_PATH = APP_DATA_DIR / "swiftdownloader.db"
SETTINGS_PATH = APP_DATA_DIR / "settings.json"
LOG_PATH = APP_DATA_DIR / "swiftdownloader.log"
DEFAULT_DOWNLOAD_DIR = get_default_download_dir()
TEMP_DIR = get_temp_dir()

# --- Download Engine Defaults ---
DEFAULT_MAX_SIMULTANEOUS_DOWNLOADS = 3
DEFAULT_CONNECTIONS_PER_DOWNLOAD = 8
DEFAULT_RETRY_COUNT = 5
DEFAULT_RETRY_DELAY_SECONDS = 5
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_CHUNK_SIZE = 8192
MIN_SEGMENT_SIZE = 1024 * 1024  # 1 MB minimum per segment
MAX_CONNECTIONS_PER_DOWNLOAD = 32
DEFAULT_SPEED_LIMIT = 0  # 0 = unlimited, in bytes/sec

# --- File Categories ---
FILE_CATEGORIES = {
    "Documents": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
                  ".txt", ".rtf", ".odt", ".ods", ".odp", ".csv", ".epub"],
    "Videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
               ".m4v", ".mpg", ".mpeg", ".3gp"],
    "Music": [".mp3", ".flac", ".aac", ".ogg", ".wma", ".wav", ".m4a",
              ".opus", ".aiff"],
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp",
               ".ico", ".tiff", ".psd", ".raw"],
    "Software": [".exe", ".msi", ".dmg", ".deb", ".rpm", ".appimage",
                 ".apk", ".app"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
                 ".tar.gz", ".tar.bz2", ".tar.xz", ".iso"],
}

def get_category_for_file(filename: str) -> str:
    """Determine the category for a given filename."""
    ext = Path(filename).suffix.lower()
    for category, extensions in FILE_CATEGORIES.items():
        if ext in extensions:
            return category
    return "Other"

# --- Architecture Detection ---
class SystemInfo:
    """Detect system architecture and OS information."""

    @staticmethod
    def get_os_architecture() -> str:
        """Get the actual OS architecture, handling WoW64."""
        if sys.platform != "win32":
            return platform.machine()
        # On Windows, detect actual OS arch even from 32-bit process
        try:
            kernel32 = ctypes.windll.kernel32
            # Try GetNativeSystemInfo first
            class SYSTEM_INFO(ctypes.Structure):
                _fields_ = [
                    ("wProcessorArchitecture", ctypes.c_ushort),
                    ("wReserved", ctypes.c_ushort),
                    ("dwPageSize", ctypes.c_ulong),
                    ("lpMinimumApplicationAddress", ctypes.c_void_p),
                    ("lpMaximumApplicationAddress", ctypes.c_void_p),
                    ("dwActiveProcessorMask", ctypes.c_ulonglong),
                    ("dwNumberOfProcessors", ctypes.c_ulong),
                    ("dwProcessorType", ctypes.c_ulong),
                    ("dwAllocationGranularity", ctypes.c_ulong),
                    ("wProcessorLevel", ctypes.c_ushort),
                    ("wProcessorRevision", ctypes.c_ushort),
                ]
            si = SYSTEM_INFO()
            kernel32.GetNativeSystemInfo(ctypes.byref(si))
            arch_map = {0: "x86", 5: "ARM", 6: "IA64", 9: "x64", 12: "ARM64"}
            return arch_map.get(si.wProcessorArchitecture, "Unknown")
        except Exception:
            # Fallback
            machine = platform.machine().lower()
            if machine in ("amd64", "x86_64"):
                return "x64"
            elif machine in ("x86", "i386", "i686"):
                return "x86"
            elif "arm" in machine or "aarch64" in machine:
                return "ARM64"
            return machine

    @staticmethod
    def get_windows_version() -> str:
        """Get Windows version string."""
        if sys.platform != "win32":
            return f"{platform.system()} {platform.release()}"
        try:
            ver = sys.getwindowsversion()
            build = ver.build
            if build >= 22000:
                return f"Windows 11 (Build {build})"
            elif build >= 10240:
                return f"Windows 10 (Build {build})"
            else:
                return f"Windows {ver.major}.{ver.minor} (Build {build})"
        except Exception:
            return platform.platform()

    @staticmethod
    def get_processor_name() -> str:
        """Get processor name."""
        return platform.processor() or "Unknown"

    @staticmethod
    def get_system_summary() -> dict:
        """Get a complete system summary."""
        return {
            "os": SystemInfo.get_windows_version(),
            "architecture": SystemInfo.get_os_architecture(),
            "processor": SystemInfo.get_processor_name(),
            "python_version": platform.python_version(),
            "python_arch": platform.architecture()[0],
            "machine": platform.machine(),
        }

# --- Settings ---
DEFAULT_SETTINGS = {
    "general": {
        "language": "English",
        "theme": "dark",
        "start_minimized": False,
        "minimize_to_tray": True,
        "start_with_windows": False,
        "show_notifications": True,
        "play_sound_on_complete": False,
    },
    "downloads": {
        "default_directory": str(DEFAULT_DOWNLOAD_DIR),
        "max_simultaneous": DEFAULT_MAX_SIMULTANEOUS_DOWNLOADS,
        "connections_per_download": DEFAULT_CONNECTIONS_PER_DOWNLOAD,
        "retry_count": DEFAULT_RETRY_COUNT,
        "retry_delay": DEFAULT_RETRY_DELAY_SECONDS,
        "speed_limit": DEFAULT_SPEED_LIMIT,
        "auto_categorize": True,
        "temp_directory": str(TEMP_DIR),
    },
    "browser": {
        "chrome_enabled": False,
        "edge_enabled": False,
        "firefox_enabled": False,
    },
    "clipboard": {
        "monitor_enabled": False,
    },
    "advanced": {
        "logging_enabled": True,
        "log_level": "INFO",
    },
}


def load_settings() -> dict:
    """Load settings from disk, merging with defaults."""
    settings = json.loads(json.dumps(DEFAULT_SETTINGS))  # deep copy
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # Merge saved into defaults
            for section, values in saved.items():
                if section in settings and isinstance(values, dict):
                    settings[section].update(values)
        except (json.JSONDecodeError, OSError):
            pass
    return settings


def save_settings(settings: dict) -> None:
    """Save settings to disk."""
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except OSError:
        pass
