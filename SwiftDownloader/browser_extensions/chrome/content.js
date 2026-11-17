/**
 * SwiftDownloader Content Script
 * Detects downloadable links on web pages.
 */

const DOWNLOAD_EXTENSIONS = [
  ".zip", ".rar", ".7z", ".tar.gz", ".exe", ".msi", ".iso",
  ".pdf", ".doc", ".docx", ".xls", ".xlsx",
  ".mp4", ".mkv", ".avi", ".mov", ".webm",
  ".mp3", ".flac", ".wav",
];

function isDownloadLink(href) {
  if (!href) return false;
  try {
    const pathname = new URL(href, window.location.origin).pathname.toLowerCase();
    return DOWNLOAD_EXTENSIONS.some((ext) => pathname.endsWith(ext));
  } catch {
    return false;
  }
}

// Add visual indicator to download links
document.querySelectorAll("a[href]").forEach((link) => {
  if (isDownloadLink(link.href)) {
    link.title = link.title || `Download with SwiftDownloader: ${link.href}`;
  }
});
