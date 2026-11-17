"""Formatting utilities for display."""


def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size."""
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.1f} {units[i]}" if i > 0 else f"{int(size)} B"


def format_speed(bytes_per_sec: float) -> str:
    """Format download speed."""
    if bytes_per_sec <= 0:
        return "0 B/s"
    return format_size(int(bytes_per_sec)) + "/s"


def format_eta(seconds: float) -> str:
    """Format estimated time remaining."""
    if seconds <= 0 or seconds > 86400 * 30:
        return "—"
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s}s"
    else:
        h, remainder = divmod(int(seconds), 3600)
        m, _ = divmod(remainder, 60)
        return f"{h}h {m}m"


def format_percentage(value: float) -> str:
    """Format percentage."""
    return f"{value:.1f}%"


def truncate_filename(name: str, max_len: int = 40) -> str:
    """Truncate a filename for display."""
    if len(name) <= max_len:
        return name
    ext_idx = name.rfind(".")
    if ext_idx > 0:
        ext = name[ext_idx:]
        base = name[:max_len - len(ext) - 3]
        return base + "..." + ext
    return name[:max_len - 3] + "..."


def sanitize_filename(name: str) -> str:
    """Sanitize a filename for Windows compatibility."""
    invalid_chars = '<>:"/\\|?*'
    for c in invalid_chars:
        name = name.replace(c, "_")
    # Remove control characters
    name = "".join(c for c in name if ord(c) >= 32)
    # Remove trailing dots and spaces (Windows issue)
    name = name.rstrip(". ")
    if not name:
        name = "download"
    return name[:255]
