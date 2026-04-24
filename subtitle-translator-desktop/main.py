"""Entrypoint for the Subtitle Translator desktop app.

Usage:
    GEMINI_API_KEY=... python main.py
"""

from __future__ import annotations

import sys

from PyQt5.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Subtitle Translator")
    app.setOrganizationName("Shinprogram")
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
