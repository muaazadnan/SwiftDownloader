"""Dashboard page — overview of download activity."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QScrollArea, QProgressBar,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.database import Database
from app.download_engine.manager import DownloadManager
from app.utils.formatting import format_size, format_speed


class StatCard(QFrame):
    """A statistics card widget."""

    def __init__(self, label: str, value: str = "0", color: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setMinimumWidth(140)

        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("statValue")
        font = QFont()
        font.setPointSize(22)
        font.setBold(True)
        self.value_label.setFont(font)
        if color:
            self.value_label.setStyleSheet(f"color: {color};")
        layout.addWidget(self.value_label)

        self.name_label = QLabel(label.upper())
        self.name_label.setObjectName("statLabel")
        layout.addWidget(self.name_label)

    def set_value(self, value: str):
        self.value_label.setText(value)


class DashboardPage(QWidget):
    """Dashboard overview page."""

    def __init__(self, db: Database, manager: DownloadManager, theme: dict, parent=None):
        super().__init__(parent)
        self.db = db
        self.manager = manager
        self.theme = theme
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(24)

        # Header
        header = QLabel("Dashboard")
        header.setObjectName("titleLabel")
        header_font = QFont()
        header_font.setPointSize(20)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        subtitle = QLabel("Overview of your download activity")
        subtitle.setObjectName("subtitleLabel")
        layout.addWidget(subtitle)

        # Stats row
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)

        self.stat_total = StatCard("Total Downloads", "0", self.theme["accent"])
        self.stat_active = StatCard("Active", "0", self.theme["accent"])
        self.stat_completed = StatCard("Completed", "0", self.theme["success"])
        self.stat_failed = StatCard("Failed", "0", self.theme["error"])
        self.stat_speed = StatCard("Speed", "0 B/s", self.theme["accent"])
        self.stat_queued = StatCard("Queued", "0", self.theme["warning"])

        for card in (self.stat_total, self.stat_active, self.stat_completed,
                     self.stat_failed, self.stat_speed, self.stat_queued):
            stats_layout.addWidget(card)

        layout.addLayout(stats_layout)

        # Recent downloads section
        recent_header = QLabel("Recent Downloads")
        recent_font = QFont()
        recent_font.setPointSize(15)
        recent_font.setBold(True)
        recent_header.setFont(recent_font)
        layout.addWidget(recent_header)

        self.recent_container = QVBoxLayout()
        self.recent_container.setSpacing(8)
        layout.addLayout(self.recent_container)

        layout.addStretch()

    def refresh(self):
        """Refresh dashboard data."""
        stats = self.db.get_stats()
        self.stat_total.set_value(str(stats.get("total", 0)))
        self.stat_active.set_value(str(stats.get("downloading", 0)))
        self.stat_completed.set_value(str(stats.get("completed", 0)))
        self.stat_failed.set_value(str(stats.get("failed", 0)))
        self.stat_queued.set_value(str(stats.get("queued", 0)))

        speed = self.manager.get_current_speed()
        self.stat_speed.set_value(format_speed(speed))

        self._refresh_recent()

    def refresh_live(self):
        """Fast refresh for active download speed."""
        speed = self.manager.get_current_speed()
        self.stat_speed.set_value(format_speed(speed))
        stats = self.db.get_stats()
        self.stat_active.set_value(str(stats.get("downloading", 0)))

    def _refresh_recent(self):
        """Refresh recent downloads list."""
        # Clear existing
        while self.recent_container.count():
            item = self.recent_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        recent = self.db.get_all_downloads()[:10]
        for dl in recent:
            card = self._create_download_card(dl)
            self.recent_container.addWidget(card)

    def _create_download_card(self, dl: dict) -> QFrame:
        """Create a compact download info card."""
        card = QFrame()
        card.setObjectName("card")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)

        # Filename
        name = QLabel(dl["filename"])
        name.setStyleSheet("font-weight: 600;")
        name.setMinimumWidth(200)
        layout.addWidget(name, stretch=3)

        # Size
        size_text = format_size(dl["total_size"]) if dl["total_size"] else "Unknown"
        size = QLabel(size_text)
        size.setObjectName("subtitleLabel")
        layout.addWidget(size, stretch=1)

        # Status
        status = dl["status"]
        status_colors = {
            "completed": self.theme["success"],
            "downloading": self.theme["accent"],
            "failed": self.theme["error"],
            "paused": self.theme["warning"],
            "queued": self.theme["text_secondary"],
            "pending": self.theme["text_muted"],
            "cancelled": self.theme["text_muted"],
        }
        color = status_colors.get(status, self.theme["text_secondary"])
        status_label = QLabel(status.capitalize())
        status_label.setStyleSheet(f"color: {color}; font-weight: 600;")
        layout.addWidget(status_label, stretch=1)

        # Progress
        if status == "downloading":
            progress = QProgressBar()
            progress.setMaximum(100)
            pct = 0
            if dl["total_size"] > 0:
                pct = int((dl["downloaded_size"] / dl["total_size"]) * 100)
            progress.setValue(pct)
            progress.setFixedWidth(120)
            layout.addWidget(progress, stretch=1)
        else:
            layout.addStretch(1)

        return card
