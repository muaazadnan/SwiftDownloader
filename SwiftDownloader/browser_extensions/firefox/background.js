/**
 * SwiftDownloader Browser Extension — Background Service Worker
 * Intercepts downloads and sends them to the native SwiftDownloader app.
 */

const NATIVE_HOST = "com.swiftdownloader.host";
const SUPPORTED_EXTENSIONS = [
  ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso",
  ".exe", ".msi", ".dmg", ".deb", ".rpm", ".appimage", ".apk",
  ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
  ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
  ".mp3", ".flac", ".aac", ".ogg", ".wav",
  ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp",
];

let enabled = true;
let nativePort = null;

// Load settings
chrome.storage.sync.get(["enabled", "supportedExtensions"], (result) => {
  if (result.enabled !== undefined) enabled = result.enabled;
});

/**
 * Check if a URL has a supported file extension.
 */
function isSupportedUrl(url) {
  if (!url) return false;
  try {
    const pathname = new URL(url).pathname.toLowerCase();
    return SUPPORTED_EXTENSIONS.some((ext) => pathname.endsWith(ext));
  } catch {
    return false;
  }
}

/**
 * Connect to native messaging host.
 */
function connectNative() {
  if (nativePort) return nativePort;
  try {
    nativePort = chrome.runtime.connectNative(NATIVE_HOST);
    nativePort.onMessage.addListener((msg) => {
      console.log("SwiftDownloader response:", msg);
    });
    nativePort.onDisconnect.addListener(() => {
      console.log("SwiftDownloader native host disconnected");
      nativePort = null;
    });
    return nativePort;
  } catch (e) {
    console.error("Failed to connect to SwiftDownloader:", e);
    return null;
  }
}

/**
 * Send a URL to SwiftDownloader via native messaging.
 */
function sendToSwiftDownloader(url, filename) {
  const port = connectNative();
  if (port) {
    port.postMessage({
      action: "download",
      url: url,
      filename: filename || "",
    });
    chrome.notifications.create({
      type: "basic",
      title: "SwiftDownloader",
      message: `Sent to SwiftDownloader: ${filename || url}`,
      iconUrl: "icons/icon48.png",
    });
  } else {
    chrome.notifications.create({
      type: "basic",
      title: "SwiftDownloader",
      message: "Could not connect to SwiftDownloader. Is it running?",
      iconUrl: "icons/icon48.png",
    });
  }
}

/**
 * Intercept downloads when enabled.
 */
chrome.downloads.onCreated.addListener((downloadItem) => {
  if (!enabled) return;
  const url = downloadItem.finalUrl || downloadItem.url;
  if (isSupportedUrl(url)) {
    // Cancel the browser download and hand it to SwiftDownloader
    chrome.downloads.cancel(downloadItem.id, () => {
      chrome.downloads.erase({ id: downloadItem.id });
      sendToSwiftDownloader(url, downloadItem.filename);
    });
  }
});

/**
 * Context menu for manual download.
 */
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "swiftdownloader-link",
    title: "Download with SwiftDownloader",
    contexts: ["link"],
  });
});

chrome.contextMenus.onClicked.addListener((info) => {
  if (info.menuItemId === "swiftdownloader-link" && info.linkUrl) {
    sendToSwiftDownloader(info.linkUrl);
  }
});

/**
 * Handle messages from popup.
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "getStatus") {
    sendResponse({ enabled, connected: nativePort !== null });
  } else if (message.action === "toggle") {
    enabled = !enabled;
    chrome.storage.sync.set({ enabled });
    sendResponse({ enabled });
  } else if (message.action === "downloadUrl") {
    sendToSwiftDownloader(message.url, message.filename);
    sendResponse({ success: true });
  }
});
