"""Centralised QSS stylesheet for the dark theme.

Kept in one place so the look-and-feel can be tweaked without touching
widget code. Colours were picked to roughly match modern video editors
(DaVinci / Premiere dark mode).
"""

DARK_QSS = """
* {
    color: #E8E8EC;
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QMainWindow, QWidget#Root {
    background-color: #121216;
}

QFrame#Card {
    background-color: #1B1B21;
    border: 1px solid #26262E;
    border-radius: 10px;
}

QLabel#HeaderTitle {
    font-size: 16px;
    font-weight: 600;
    color: #F5F5F7;
}

QLabel#Muted {
    color: #8A8A94;
}

QLabel#TimeLabel {
    color: #C9C9D1;
    font-variant-numeric: tabular-nums;
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 12px;
}

QLabel#VideoArea {
    background-color: #000000;
    border-radius: 8px;
}

QLabel#SubtitleOverlay {
    color: #FFFFFF;
    background-color: rgba(0, 0, 0, 160);
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 18px;
    font-weight: 500;
}

QPushButton {
    background-color: #2A2A33;
    border: 1px solid #33333D;
    color: #EDEDF1;
    padding: 7px 14px;
    border-radius: 8px;
}
QPushButton:hover { background-color: #34343F; }
QPushButton:pressed { background-color: #1F1F27; }
QPushButton:disabled { color: #6A6A73; background-color: #22222A; }

QPushButton#Primary {
    background-color: #4F46E5;
    border: 1px solid #6366F1;
    color: #FFFFFF;
    font-weight: 600;
}
QPushButton#Primary:hover { background-color: #5B52EE; }
QPushButton#Primary:pressed { background-color: #3F38C8; }

QPushButton#IconBtn {
    padding: 6px 10px;
    min-width: 34px;
}

QLineEdit, QPlainTextEdit, QTextEdit {
    background-color: #14141A;
    border: 1px solid #2A2A33;
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: #4F46E5;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {
    border: 1px solid #6366F1;
}

QTableView, QTableWidget {
    background-color: #14141A;
    border: 1px solid #26262E;
    border-radius: 8px;
    gridline-color: #22222A;
    alternate-background-color: #17171D;
    selection-background-color: #2C2A6B;
    selection-color: #FFFFFF;
}
QHeaderView::section {
    background-color: #1B1B22;
    color: #AEAEB8;
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid #26262E;
}
QTableView::item { padding: 6px 8px; }

QSlider::groove:horizontal {
    height: 6px;
    background: #26262E;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #6366F1;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #F5F5F7;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QStatusBar {
    background-color: #0F0F14;
    color: #8A8A94;
    border-top: 1px solid #22222A;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #33333D;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #44444F; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QSplitter::handle {
    background-color: #0F0F14;
}
"""
