"""About page."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.config import APP_NAME, APP_VERSION, APP_TAGLINE, APP_LICENSE


class AboutPage(QWidget):
    """About / Info page."""

    def __init__(self, theme: dict, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(24)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Title
        header = QLabel("About")
        header.setObjectName("titleLabel")
        header_font = QFont()
        header_font.setPointSize(20)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        # App card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)

        name_label = QLabel(APP_NAME)
        name_font = QFont()
        name_font.setPointSize(28)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setStyleSheet(f"color: {self.theme['accent']};")
        card_layout.addWidget(name_label)

        tagline = QLabel(APP_TAGLINE)
        tagline_font = QFont()
        tagline_font.setPointSize(14)
        tagline.setFont(tagline_font)
        tagline.setObjectName("subtitleLabel")
        card_layout.addWidget(tagline)

        version = QLabel(f"Version {APP_VERSION}")
        version.setObjectName("subtitleLabel")
        card_layout.addWidget(version)

        card_layout.addSpacing(16)

        desc = QLabel(
            f"{APP_NAME} is a free, open-source download manager for Windows.\n\n"
            "Features:\n"
            "• Multi-connection accelerated downloads\n"
            "• Pause, resume and auto-retry\n"
            "• Download queue and scheduler\n"
            "• Browser integration (Chrome, Edge, Firefox)\n"
            "• Clipboard monitoring\n"
            "• Automatic file categorization\n"
            "• SHA-256 file verification\n"
            "• Dark and light themes\n"
            "• System tray support\n\n"
            f"License: {APP_LICENSE}\n\n"
            "100% free. No ads. No subscriptions. No premium plans.\n"
            "Free forever."
        )
        desc.setWordWrap(True)
        desc.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(desc)

        layout.addWidget(card)
        layout.addStretch()

    def refresh(self):
        pass
