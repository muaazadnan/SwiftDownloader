"""Add Download dialog."""
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QComboBox, QFileDialog, QCheckBox, QMessageBox, QFormLayout,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.config import get_category_for_file, MAX_CONNECTIONS_PER_DOWNLOAD
from app.download_engine.manager import DownloadManager


class AddDownloadDialog(QDialog):
    """Dialog to add a new download."""

    def __init__(self, manager: DownloadManager, settings: dict,
                 theme: dict, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.settings = settings
        self.theme = theme
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Add Download")
        self.setMinimumWidth(550)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Add New Download")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)

        # URL
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/file.zip")
        self.url_input.setFixedHeight(40)
        form.addRow("URL:", self.url_input)

        # Filename (optional)
        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("Auto-detect from URL")
        form.addRow("Filename:", self.filename_input)

        # Save location
        dir_row = QHBoxLayout()
        self.dir_input = QLineEdit()
        self.dir_input.setText(self.settings["downloads"]["default_directory"])
        self.dir_input.setReadOnly(True)
        dir_row.addWidget(self.dir_input)
        browse = QPushButton("Browse")
        browse.setObjectName("secondaryBtn")
        browse.setFixedWidth(80)
        browse.clicked.connect(self._browse)
        dir_row.addWidget(browse)
        form.addRow("Save to:", dir_row)

        # Connections
        self.connections_spin = QSpinBox()
        self.connections_spin.setRange(1, MAX_CONNECTIONS_PER_DOWNLOAD)
        self.connections_spin.setValue(
            self.settings["downloads"]["connections_per_download"]
        )
        form.addRow("Connections:", self.connections_spin)

        # Start immediately
        self.start_now = QCheckBox("Start download immediately")
        self.start_now.setChecked(True)
        form.addRow(self.start_now)

        # SHA-256 (optional)
        self.hash_input = QLineEdit()
        self.hash_input.setPlaceholderText("Optional — verify file after download")
        form.addRow("SHA-256:", self.hash_input)

        layout.addLayout(form)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        add_btn = QPushButton("Add Download")
        add_btn.setFixedWidth(140)
        add_btn.clicked.connect(self._add)
        btn_row.addWidget(add_btn)

        layout.addLayout(btn_row)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            self.dir_input.setText(folder)

    def _add(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL.")
            return

        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, "Error", "URL must start with http:// or https://")
            return

        filename = self.filename_input.text().strip() or None
        save_path = self.dir_input.text()
        connections = self.connections_spin.value()
        start_now = self.start_now.isChecked()

        try:
            self.manager.add_download(
                url=url,
                filename=filename,
                save_path=save_path,
                connections=connections,
                start_immediately=start_now,
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add download:\n{e}")
