"""Main application window."""
import os
import sys
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QFrame, QSplitter, QApplication, QSystemTrayIcon,
    QMenu, QMessageBox, QFileDialog,
)
from PySide6.QtCore import Qt, QSize, Signal, QTimer
from PySide6.QtGui import QIcon, QAction, QFont

from app.config import APP_NAME, APP_VERSION, APP_TAGLINE, load_settings, save_settings
from app.database import Database
from app.download_engine.manager import DownloadManager
from app.download_engine.engine import DownloadProgress
from app.scheduler import DownloadScheduler
from app.services.clipboard_monitor import ClipboardMonitor
from app.ui.themes import get_theme, get_stylesheet
from app.ui.pages.dashboard import DashboardPage
from app.ui.pages.downloads import DownloadsPage
from app.ui.pages.settings_page import SettingsPage
from app.ui.pages.about_page import AboutPage
from app.ui.dialogs.add_download import AddDownloadDialog
from app.utils.logging_setup import setup_logging

logger = logging.getLogger("SwiftDownloader.MainWindow")


class SidebarButton(QPushButton):
    """Sidebar navigation button."""

    def __init__(self, text: str, icon_text: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("sidebarButton")
        display = f"  {icon_text}  {text}" if icon_text else f"  {text}"
        self.setText(display)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)
        self._active = False

    def set_active(self, active: bool):
        self._active = active
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)


class MainWindow(QMainWindow):
    """Main SwiftDownloader window."""

    def __init__(self):
        super().__init__()

        # Initialize core components
        self.settings = load_settings()
        self.db = Database.get_instance()
        self.manager = DownloadManager(self.db)
        self.scheduler = DownloadScheduler(self.manager, self.db)
        self.clipboard_monitor = ClipboardMonitor()

        # Setup logging
        log_level = self.settings.get("advanced", {}).get("log_level", "INFO")
        setup_logging(log_level)

        # Apply theme
        self.theme = get_theme(self.settings["general"]["theme"])

        self._setup_ui()
        self._setup_tray()
        self._connect_signals()

        # Start services
        self.manager.start()
        self.scheduler.start()
        if self.settings["clipboard"]["monitor_enabled"]:
            self.clipboard_monitor.on_url_detected = self._on_clipboard_url
            self.clipboard_monitor.start()

        # Refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_active_downloads)
        self._refresh_timer.start(1000)

    def _setup_ui(self):
        """Build the main UI layout."""
        self.setWindowTitle(f"{APP_NAME} — {APP_TAGLINE}")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        # Apply stylesheet
        self.setStyleSheet(get_stylesheet(self.theme))

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Sidebar ---
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 16, 8, 16)
        sidebar_layout.setSpacing(2)

        # App title
        title = QLabel(APP_NAME)
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        sidebar_layout.addWidget(title)

        tagline = QLabel(APP_TAGLINE)
        tagline.setObjectName("subtitleLabel")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(tagline)

        sidebar_layout.addSpacing(24)

        # Navigation buttons
        self.nav_buttons = []
        nav_items = [
            ("Dashboard", "📊"),
            ("All Downloads", "📥"),
            ("Downloading", "⬇️"),
            ("Completed", "✅"),
            ("Queue", "📋"),
            ("Scheduled", "⏰"),
            ("Failed", "❌"),
            ("Categories", "📁"),
            ("Settings", "⚙️"),
            ("About", "ℹ️"),
        ]
        for text, icon in nav_items:
            btn = SidebarButton(text, icon)
            btn.clicked.connect(lambda checked=False, t=text: self._navigate(t))
            sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sidebar_layout.addStretch()

        # Add Download button
        add_btn = QPushButton("  ＋  Add Download")
        add_btn.setFixedHeight(44)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._show_add_download)
        sidebar_layout.addWidget(add_btn)

        main_layout.addWidget(sidebar)

        # --- Content Area ---
        self.content_stack = QStackedWidget()
        self.content_stack.setContentsMargins(0, 0, 0, 0)

        # Create pages
        self.dashboard_page = DashboardPage(self.db, self.manager, self.theme)
        self.all_downloads_page = DownloadsPage(
            self.db, self.manager, "all", self.theme
        )
        self.downloading_page = DownloadsPage(
            self.db, self.manager, "downloading", self.theme
        )
        self.completed_page = DownloadsPage(
            self.db, self.manager, "completed", self.theme
        )
        self.queue_page = DownloadsPage(
            self.db, self.manager, "queued", self.theme
        )
        self.scheduled_page = DownloadsPage(
            self.db, self.manager, "scheduled", self.theme
        )
        self.failed_page = DownloadsPage(
            self.db, self.manager, "failed", self.theme
        )
        self.categories_page = DownloadsPage(
            self.db, self.manager, "categories", self.theme
        )
        self.settings_page = SettingsPage(self.settings, self.theme)
        self.about_page = AboutPage(self.theme)

        self.content_stack.addWidget(self.dashboard_page)     # 0
        self.content_stack.addWidget(self.all_downloads_page)  # 1
        self.content_stack.addWidget(self.downloading_page)    # 2
        self.content_stack.addWidget(self.completed_page)      # 3
        self.content_stack.addWidget(self.queue_page)          # 4
        self.content_stack.addWidget(self.scheduled_page)      # 5
        self.content_stack.addWidget(self.failed_page)         # 6
        self.content_stack.addWidget(self.categories_page)     # 7
        self.content_stack.addWidget(self.settings_page)       # 8
        self.content_stack.addWidget(self.about_page)          # 9

        main_layout.addWidget(self.content_stack)

        # Set initial page
        self._navigate("Dashboard")

    def _setup_tray(self):
        """Setup system tray icon."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray_icon = QSystemTrayIcon(self)
        # Use a default icon — real icon comes from assets
        self.tray_icon.setToolTip(APP_NAME)

        tray_menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)

        add_action = QAction("Add Download", self)
        add_action.triggered.connect(self._show_add_download)
        tray_menu.addAction(add_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _connect_signals(self):
        """Connect manager callbacks."""
        self.manager.on_download_progress = self._on_download_progress
        self.manager.on_download_complete = self._on_download_complete
        self.manager.on_download_error = self._on_download_error
        self.manager.on_download_added = self._on_download_added

        # Settings page signals
        self.settings_page.settings_changed.connect(self._on_settings_changed)

    def _navigate(self, page_name: str):
        """Navigate to a page."""
        page_map = {
            "Dashboard": 0, "All Downloads": 1, "Downloading": 2,
            "Completed": 3, "Queue": 4, "Scheduled": 5,
            "Failed": 6, "Categories": 7, "Settings": 8, "About": 9,
        }
        idx = page_map.get(page_name, 0)
        self.content_stack.setCurrentIndex(idx)

        # Update active button
        for i, btn in enumerate(self.nav_buttons):
            btn.set_active(i == idx)

        # Refresh page data
        current = self.content_stack.currentWidget()
        if hasattr(current, "refresh"):
            current.refresh()

    def _show_add_download(self):
        """Show the Add Download dialog."""
        dialog = AddDownloadDialog(self.manager, self.settings, self.theme, self)
        if dialog.exec():
            self._navigate("All Downloads")

    def _on_clipboard_url(self, url: str):
        """Handle URL detected from clipboard."""
        if self.tray_icon:
            self.tray_icon.showMessage(
                "URL Detected",
                f"Download: {url[:60]}...?",
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )

    def _on_download_progress(self, download_id: int, progress: DownloadProgress):
        """Handle download progress update."""
        pass  # UI pages poll from DB via refresh timer

    def _on_download_complete(self, download_id: int):
        """Handle download completion."""
        dl = self.db.get_download(download_id)
        if dl and self.settings["general"]["show_notifications"]:
            if hasattr(self, "tray_icon") and self.tray_icon:
                self.tray_icon.showMessage(
                    "Download Complete",
                    f"{dl['filename']}",
                    QSystemTrayIcon.MessageIcon.Information,
                    3000,
                )

    def _on_download_error(self, download_id: int, error: str):
        """Handle download error."""
        dl = self.db.get_download(download_id)
        if dl:
            logger.error(f"Download failed: {dl['filename']} — {error}")

    def _on_download_added(self, download_id: int):
        """Handle new download added."""
        pass

    def _refresh_active_downloads(self):
        """Periodic refresh of UI for active downloads."""
        current = self.content_stack.currentWidget()
        if hasattr(current, "refresh_live"):
            current.refresh_live()

    def _on_settings_changed(self, new_settings: dict):
        """Apply changed settings."""
        self.settings = new_settings
        save_settings(new_settings)
        self.manager.update_settings(new_settings)

        # Apply theme change
        new_theme = get_theme(new_settings["general"]["theme"])
        if new_theme["name"] != self.theme["name"]:
            self.theme = new_theme
            self.setStyleSheet(get_stylesheet(self.theme))

        # Clipboard monitor
        if new_settings["clipboard"]["monitor_enabled"]:
            if not self.clipboard_monitor.is_enabled:
                self.clipboard_monitor.on_url_detected = self._on_clipboard_url
                self.clipboard_monitor.start()
        else:
            self.clipboard_monitor.stop()

    def _tray_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.raise_()
            self.activateWindow()

    def _quit_app(self):
        """Clean shutdown."""
        self.manager.stop()
        self.scheduler.stop()
        self.clipboard_monitor.stop()
        QApplication.quit()

    def closeEvent(self, event):
        """Handle window close — minimize to tray or quit."""
        if self.settings["general"]["minimize_to_tray"]:
            event.ignore()
            self.hide()
        else:
            self._quit_app()
            event.accept()
