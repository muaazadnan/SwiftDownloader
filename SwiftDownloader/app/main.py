"""SwiftDownloader — Free. Fast. Unlimited.

Main entry point for the application.
"""
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.ui.main_window import MainWindow
from app.config import APP_NAME


def main():
    """Launch SwiftDownloader."""
    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("SwiftDownloader")

    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Create and show main window
    window = MainWindow()

    # Check for start-minimized flag
    if "--minimized" in sys.argv:
        window.hide()
    else:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
