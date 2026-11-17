"""Downloads list page — shared by multiple views."""
import os
import subprocess
import sys
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QMenu, QFrame, QLineEdit, QComboBox,
    QAbstractItemView, QMessageBox, QFileDialog,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QAction, QCursor

from app.database import Database
from app.download_engine.manager import DownloadManager
from app.utils.formatting import format_size, format_speed, format_eta, format_percentage


class DownloadsPage(QWidget):
    """Displays a filtered table of downloads."""

    def __init__(self, db: Database, manager: DownloadManager,
                 filter_mode: str, theme: dict, parent=None):
        super().__init__(parent)
        self.db = db
        self.manager = manager
        self.filter_mode = filter_mode
        self.theme = theme
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # Header
        titles = {
            "all": "All Downloads",
            "downloading": "Active Downloads",
            "completed": "Completed",
            "queued": "Download Queue",
            "scheduled": "Scheduled Downloads",
            "failed": "Failed Downloads",
            "categories": "Categories",
        }
        header = QLabel(titles.get(self.filter_mode, "Downloads"))
        header.setObjectName("titleLabel")
        header_font = QFont()
        header_font.setPointSize(20)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        # Toolbar row
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search downloads...")
        self.search_input.setFixedHeight(36)
        self.search_input.setMinimumWidth(250)
        self.search_input.textChanged.connect(self.refresh)
        toolbar.addWidget(self.search_input)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Newest First", "Oldest First", "Name A-Z",
                                   "Name Z-A", "Size ↑", "Size ↓"])
        self.sort_combo.setFixedHeight(36)
        self.sort_combo.currentTextChanged.connect(self.refresh)
        toolbar.addWidget(self.sort_combo)

        toolbar.addStretch()

        # Action buttons
        if self.filter_mode in ("all", "downloading", "queued"):
            pause_all = QPushButton("Pause All")
            pause_all.setObjectName("secondaryBtn")
            pause_all.clicked.connect(self._pause_all)
            toolbar.addWidget(pause_all)

            resume_all = QPushButton("Resume All")
            resume_all.setObjectName("secondaryBtn")
            resume_all.clicked.connect(self._resume_all)
            toolbar.addWidget(resume_all)

        if self.filter_mode in ("completed", "all"):
            clear_btn = QPushButton("Clear Completed")
            clear_btn.setObjectName("secondaryBtn")
            clear_btn.clicked.connect(self._clear_completed)
            toolbar.addWidget(clear_btn)

        layout.addLayout(toolbar)

        # Downloads table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "File Name", "Size", "Downloaded", "Progress", "Speed", "Status", "ETA"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 7):
            self.table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Status bar
        self.status_label = QLabel("0 downloads")
        self.status_label.setObjectName("subtitleLabel")
        layout.addWidget(self.status_label)

    def refresh(self):
        """Refresh the downloads table."""
        search = self.search_input.text().strip()

        if search:
            downloads = self.db.search_downloads(search)
        elif self.filter_mode == "all":
            downloads = self.db.get_all_downloads()
        elif self.filter_mode == "categories":
            downloads = self.db.get_all_downloads()
        else:
            status_map = {
                "downloading": "downloading",
                "completed": "completed",
                "queued": "queued",
                "scheduled": "pending",
                "failed": "failed",
            }
            status = status_map.get(self.filter_mode, self.filter_mode)
            downloads = self.db.get_downloads_by_status(status)

        # Sorting
        sort_text = self.sort_combo.currentText()
        if sort_text == "Newest First":
            downloads.sort(key=lambda d: d.get("created_at", ""), reverse=True)
        elif sort_text == "Oldest First":
            downloads.sort(key=lambda d: d.get("created_at", ""))
        elif sort_text == "Name A-Z":
            downloads.sort(key=lambda d: d["filename"].lower())
        elif sort_text == "Name Z-A":
            downloads.sort(key=lambda d: d["filename"].lower(), reverse=True)
        elif sort_text == "Size ↑":
            downloads.sort(key=lambda d: d.get("total_size", 0))
        elif sort_text == "Size ↓":
            downloads.sort(key=lambda d: d.get("total_size", 0), reverse=True)

        self._populate_table(downloads)
        self.status_label.setText(f"{len(downloads)} downloads")

    def refresh_live(self):
        """Fast refresh for active downloads only."""
        if self.filter_mode in ("downloading", "all"):
            self.refresh()

    def _populate_table(self, downloads):
        """Fill the table with download data."""
        self.table.setRowCount(len(downloads))
        for row, dl in enumerate(downloads):
            # Filename
            name_item = QTableWidgetItem(dl["filename"])
            name_item.setData(Qt.ItemDataRole.UserRole, dl["id"])
            self.table.setItem(row, 0, name_item)

            # Size
            total = dl.get("total_size", 0)
            self.table.setItem(row, 1, QTableWidgetItem(
                format_size(total) if total else "Unknown"
            ))

            # Downloaded
            downloaded = dl.get("downloaded_size", 0)
            self.table.setItem(row, 2, QTableWidgetItem(format_size(downloaded)))

            # Progress
            pct = 0
            if total > 0:
                pct = (downloaded / total) * 100
            self.table.setItem(row, 3, QTableWidgetItem(f"{pct:.1f}%"))

            # Speed (only for active)
            speed_text = ""
            if dl["status"] == "downloading":
                task = self.manager.get_active_tasks().get(dl["id"])
                if task:
                    elapsed = 1  # placeholder
                    speed_text = "—"
            self.table.setItem(row, 4, QTableWidgetItem(speed_text))

            # Status
            status = dl.get("status", "unknown")
            status_item = QTableWidgetItem(status.capitalize())
            status_colors = {
                "completed": self.theme["success"],
                "downloading": self.theme["accent"],
                "failed": self.theme["error"],
                "paused": self.theme["warning"],
                "queued": self.theme["text_secondary"],
            }
            color = status_colors.get(status)
            if color:
                from PySide6.QtGui import QColor
                status_item.setForeground(QColor(color))
            self.table.setItem(row, 5, status_item)

            # ETA
            self.table.setItem(row, 6, QTableWidgetItem(""))

    def _get_selected_ids(self):
        """Get download IDs of selected rows."""
        ids = []
        for item in self.table.selectedItems():
            if item.column() == 0:
                did = item.data(Qt.ItemDataRole.UserRole)
                if did:
                    ids.append(did)
        return ids

    def _show_context_menu(self, pos):
        """Show right-click context menu."""
        ids = self._get_selected_ids()
        if not ids:
            return

        menu = QMenu(self)
        dl = self.db.get_download(ids[0])
        if not dl:
            return

        status = dl["status"]

        if status in ("paused", "queued", "pending"):
            resume_action = menu.addAction("▶  Resume")
            resume_action.triggered.connect(lambda: self._action_resume(ids))

        if status == "downloading":
            pause_action = menu.addAction("⏸  Pause")
            pause_action.triggered.connect(lambda: self._action_pause(ids))

        if status == "failed":
            retry_action = menu.addAction("🔄  Retry")
            retry_action.triggered.connect(lambda: self._action_retry(ids))

        if status in ("downloading", "paused", "queued", "pending"):
            cancel_action = menu.addAction("⏹  Cancel")
            cancel_action.triggered.connect(lambda: self._action_cancel(ids))

        menu.addSeparator()

        if status == "completed":
            open_action = menu.addAction("📂  Open File")
            open_action.triggered.connect(lambda: self._open_file(ids[0]))

            folder_action = menu.addAction("📁  Open Folder")
            folder_action.triggered.connect(lambda: self._open_folder(ids[0]))

        copy_url = menu.addAction("📋  Copy URL")
        copy_url.triggered.connect(lambda: self._copy_url(ids[0]))

        menu.addSeparator()

        delete_action = menu.addAction("🗑  Delete")
        delete_action.triggered.connect(lambda: self._action_delete(ids))

        menu.exec(QCursor.pos())

    def _action_pause(self, ids):
        for did in ids:
            self.manager.pause_download(did)
        self.refresh()

    def _action_resume(self, ids):
        for did in ids:
            self.manager.resume_download(did)
        self.refresh()

    def _action_cancel(self, ids):
        for did in ids:
            self.manager.cancel_download(did)
        self.refresh()

    def _action_retry(self, ids):
        for did in ids:
            self.manager.retry_download(did)
        self.refresh()

    def _action_delete(self, ids):
        reply = QMessageBox.question(
            self, "Delete Downloads",
            f"Delete {len(ids)} download(s)? Files on disk will not be removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            for did in ids:
                self.manager.delete_download(did, delete_file=False)
            self.refresh()

    def _open_file(self, download_id):
        dl = self.db.get_download(download_id)
        if dl:
            path = os.path.join(dl["save_path"], dl["filename"])
            if os.path.exists(path):
                if sys.platform == "win32":
                    os.startfile(path)
                else:
                    subprocess.Popen(["xdg-open", path])

    def _open_folder(self, download_id):
        dl = self.db.get_download(download_id)
        if dl:
            folder = dl["save_path"]
            if os.path.exists(folder):
                if sys.platform == "win32":
                    os.startfile(folder)
                else:
                    subprocess.Popen(["xdg-open", folder])

    def _copy_url(self, download_id):
        dl = self.db.get_download(download_id)
        if dl:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(dl["url"])

    def _pause_all(self):
        active = self.db.get_downloads_by_status("downloading")
        for dl in active:
            self.manager.pause_download(dl["id"])
        self.refresh()

    def _resume_all(self):
        paused = self.db.get_downloads_by_status("paused")
        for dl in paused:
            self.manager.resume_download(dl["id"])
        self.refresh()

    def _clear_completed(self):
        completed = self.db.get_downloads_by_status("completed")
        for dl in completed:
            self.db.delete_download(dl["id"])
        self.refresh()
