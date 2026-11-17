"""Settings page."""
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QComboBox,
    QSpinBox, QCheckBox, QPushButton, QLineEdit, QFileDialog,
    QScrollArea, QGroupBox, QFormLayout, QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from app.config import (
    DEFAULT_SETTINGS, DEFAULT_MAX_SIMULTANEOUS_DOWNLOADS,
    MAX_CONNECTIONS_PER_DOWNLOAD, SystemInfo,
)
from app.database import Database


class SettingsPage(QWidget):
    """Application settings page."""

    settings_changed = Signal(dict)

    def __init__(self, settings: dict, theme: dict, parent=None):
        super().__init__(parent)
        self.settings = json.loads(json.dumps(settings))  # deep copy
        self.theme = theme
        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(24)

        header = QLabel("Settings")
        header.setObjectName("titleLabel")
        header_font = QFont()
        header_font.setPointSize(20)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        # --- General ---
        general_group = QGroupBox("General")
        general_layout = QFormLayout()
        general_layout.setSpacing(12)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        general_layout.addRow("Theme:", self.theme_combo)

        self.start_minimized = QCheckBox("Start minimized")
        general_layout.addRow(self.start_minimized)

        self.minimize_to_tray = QCheckBox("Minimize to system tray on close")
        general_layout.addRow(self.minimize_to_tray)

        self.start_with_windows = QCheckBox("Start with Windows")
        general_layout.addRow(self.start_with_windows)

        self.show_notifications = QCheckBox("Show download notifications")
        general_layout.addRow(self.show_notifications)

        self.play_sound = QCheckBox("Play sound on download complete")
        general_layout.addRow(self.play_sound)

        general_group.setLayout(general_layout)
        layout.addWidget(general_group)

        # --- Downloads ---
        dl_group = QGroupBox("Downloads")
        dl_layout = QFormLayout()
        dl_layout.setSpacing(12)

        dir_row = QHBoxLayout()
        self.download_dir = QLineEdit()
        self.download_dir.setReadOnly(True)
        dir_row.addWidget(self.download_dir)
        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("secondaryBtn")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_directory)
        dir_row.addWidget(browse_btn)
        dl_layout.addRow("Download directory:", dir_row)

        self.max_simultaneous = QSpinBox()
        self.max_simultaneous.setRange(1, 20)
        dl_layout.addRow("Max simultaneous downloads:", self.max_simultaneous)

        self.connections_per = QSpinBox()
        self.connections_per.setRange(1, MAX_CONNECTIONS_PER_DOWNLOAD)
        dl_layout.addRow("Connections per download:", self.connections_per)

        self.retry_count = QSpinBox()
        self.retry_count.setRange(0, 20)
        dl_layout.addRow("Retry attempts:", self.retry_count)

        self.speed_limit = QSpinBox()
        self.speed_limit.setRange(0, 999999)
        self.speed_limit.setSuffix(" KB/s (0 = unlimited)")
        dl_layout.addRow("Speed limit:", self.speed_limit)

        self.auto_categorize = QCheckBox("Automatically categorize downloads")
        dl_layout.addRow(self.auto_categorize)

        dl_group.setLayout(dl_layout)
        layout.addWidget(dl_group)

        # --- Browser Integration ---
        browser_group = QGroupBox("Browser Integration")
        browser_layout = QFormLayout()
        browser_layout.setSpacing(12)

        self.chrome_enabled = QCheckBox("Google Chrome")
        browser_layout.addRow(self.chrome_enabled)

        self.edge_enabled = QCheckBox("Microsoft Edge")
        browser_layout.addRow(self.edge_enabled)

        self.firefox_enabled = QCheckBox("Mozilla Firefox")
        browser_layout.addRow(self.firefox_enabled)

        browser_group.setLayout(browser_layout)
        layout.addWidget(browser_group)

        # --- Clipboard ---
        clip_group = QGroupBox("Clipboard")
        clip_layout = QFormLayout()
        self.clipboard_enabled = QCheckBox("Monitor clipboard for download links")
        clip_layout.addRow(self.clipboard_enabled)
        clip_group.setLayout(clip_layout)
        layout.addWidget(clip_group)

        # --- Advanced ---
        adv_group = QGroupBox("Advanced")
        adv_layout = QFormLayout()
        adv_layout.setSpacing(12)

        self.logging_enabled = QCheckBox("Enable logging")
        adv_layout.addRow(self.logging_enabled)

        backup_btn = QPushButton("Backup Database")
        backup_btn.setObjectName("secondaryBtn")
        backup_btn.setFixedWidth(160)
        backup_btn.clicked.connect(self._backup_database)
        adv_layout.addRow(backup_btn)

        reset_btn = QPushButton("Reset All Settings")
        reset_btn.setObjectName("dangerBtn")
        reset_btn.setFixedWidth(160)
        reset_btn.clicked.connect(self._reset_settings)
        adv_layout.addRow(reset_btn)

        adv_group.setLayout(adv_layout)
        layout.addWidget(adv_group)

        # --- System Info ---
        sys_group = QGroupBox("System Information")
        sys_layout = QFormLayout()
        info = SystemInfo.get_system_summary()
        for key, val in info.items():
            sys_layout.addRow(f"{key.replace('_', ' ').title()}:", QLabel(str(val)))
        sys_group.setLayout(sys_layout)
        layout.addWidget(sys_group)

        # Save button
        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = QPushButton("Save Settings")
        save_btn.setFixedHeight(44)
        save_btn.setFixedWidth(180)
        save_btn.clicked.connect(self._save)
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)

        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _load_values(self):
        """Populate widgets from current settings."""
        g = self.settings["general"]
        self.theme_combo.setCurrentText(g["theme"])
        self.start_minimized.setChecked(g["start_minimized"])
        self.minimize_to_tray.setChecked(g["minimize_to_tray"])
        self.start_with_windows.setChecked(g["start_with_windows"])
        self.show_notifications.setChecked(g["show_notifications"])
        self.play_sound.setChecked(g["play_sound_on_complete"])

        d = self.settings["downloads"]
        self.download_dir.setText(d["default_directory"])
        self.max_simultaneous.setValue(d["max_simultaneous"])
        self.connections_per.setValue(d["connections_per_download"])
        self.retry_count.setValue(d["retry_count"])
        self.speed_limit.setValue(d["speed_limit"] // 1024)
        self.auto_categorize.setChecked(d["auto_categorize"])

        b = self.settings["browser"]
        self.chrome_enabled.setChecked(b["chrome_enabled"])
        self.edge_enabled.setChecked(b["edge_enabled"])
        self.firefox_enabled.setChecked(b["firefox_enabled"])

        self.clipboard_enabled.setChecked(self.settings["clipboard"]["monitor_enabled"])
        self.logging_enabled.setChecked(self.settings["advanced"]["logging_enabled"])

    def _save(self):
        """Save settings and emit signal."""
        self.settings["general"]["theme"] = self.theme_combo.currentText()
        self.settings["general"]["start_minimized"] = self.start_minimized.isChecked()
        self.settings["general"]["minimize_to_tray"] = self.minimize_to_tray.isChecked()
        self.settings["general"]["start_with_windows"] = self.start_with_windows.isChecked()
        self.settings["general"]["show_notifications"] = self.show_notifications.isChecked()
        self.settings["general"]["play_sound_on_complete"] = self.play_sound.isChecked()

        self.settings["downloads"]["default_directory"] = self.download_dir.text()
        self.settings["downloads"]["max_simultaneous"] = self.max_simultaneous.value()
        self.settings["downloads"]["connections_per_download"] = self.connections_per.value()
        self.settings["downloads"]["retry_count"] = self.retry_count.value()
        self.settings["downloads"]["speed_limit"] = self.speed_limit.value() * 1024
        self.settings["downloads"]["auto_categorize"] = self.auto_categorize.isChecked()

        self.settings["browser"]["chrome_enabled"] = self.chrome_enabled.isChecked()
        self.settings["browser"]["edge_enabled"] = self.edge_enabled.isChecked()
        self.settings["browser"]["firefox_enabled"] = self.firefox_enabled.isChecked()

        self.settings["clipboard"]["monitor_enabled"] = self.clipboard_enabled.isChecked()
        self.settings["advanced"]["logging_enabled"] = self.logging_enabled.isChecked()

        self.settings_changed.emit(self.settings)
        QMessageBox.information(self, "Settings", "Settings saved successfully.")

    def _browse_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Directory")
        if folder:
            self.download_dir.setText(folder)

    def _backup_database(self):
        try:
            db = Database.get_instance()
            path = db.backup()
            QMessageBox.information(
                self, "Backup", f"Database backed up to:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Backup Error", str(e))

    def _reset_settings(self):
        reply = QMessageBox.question(
            self, "Reset Settings",
            "Reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.settings = json.loads(json.dumps(DEFAULT_SETTINGS))
            self._load_values()
            self.settings_changed.emit(self.settings)

    def refresh(self):
        pass
