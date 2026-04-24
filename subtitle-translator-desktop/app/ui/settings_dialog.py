"""Settings dialog for API key, prompt, font, batch size and delay.

The dialog edits an :class:`AppConfig` in place. Callers should call
:meth:`AppConfig.save` afterwards to persist the changes.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_PROMPT,
    DEFAULT_REQUEST_DELAY_MS,
    AppConfig,
)


class SettingsDialog(QDialog):
    """Modal settings dialog. Mutates ``config`` only on ``accept``."""

    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(640, 560)
        self._config = config

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setSpacing(10)
        root.addLayout(form)

        # --- API key ---
        self.api_edit = QLineEdit(config.api_key)
        self.api_edit.setEchoMode(QLineEdit.Password)
        self.api_edit.setPlaceholderText("Paste your Gemini API key")
        show_btn = QPushButton("Show")
        show_btn.setCheckable(True)
        show_btn.setFixedWidth(60)
        show_btn.toggled.connect(self._toggle_api_visibility)
        api_row = QHBoxLayout()
        api_row.addWidget(self.api_edit, 1)
        api_row.addWidget(show_btn)
        api_widget = QWidget()
        api_widget.setLayout(api_row)
        form.addRow("Gemini API key:", api_widget)

        # --- Target language ---
        self.target_edit = QLineEdit(config.target_language)
        self.target_edit.setPlaceholderText("e.g. Vietnamese, English, Japanese")
        form.addRow("Target language:", self.target_edit)

        # --- Prompt ---
        self.prompt_edit = QPlainTextEdit(config.prompt)
        self.prompt_edit.setPlaceholderText(DEFAULT_PROMPT)
        self.prompt_edit.setMinimumHeight(100)
        form.addRow("Translation prompt:", self.prompt_edit)

        # --- Font family + size ---
        self.font_family = QComboBox()
        families = sorted(QFontDatabase().families())
        self.font_family.addItems(families)
        if config.font_family in families:
            self.font_family.setCurrentText(config.font_family)
        else:
            # Add the stored family at the top so the user can see what
            # they set even if it's not installed on this machine.
            self.font_family.insertItem(0, config.font_family)
            self.font_family.setCurrentIndex(0)

        self.font_size = QSpinBox()
        self.font_size.setRange(8, 72)
        self.font_size.setValue(config.font_size_px)
        self.font_size.setSuffix(" px")

        font_row = QHBoxLayout()
        font_row.addWidget(self.font_family, 1)
        font_row.addWidget(self.font_size)
        font_widget = QWidget()
        font_widget.setLayout(font_row)
        form.addRow("Overlay font:", font_widget)

        # --- Batch size ---
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 200)
        self.batch_spin.setValue(config.batch_size)
        self.batch_spin.setSuffix(" lines / request")
        form.addRow("Batch size:", self.batch_spin)

        # --- Delay ---
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 60000)
        self.delay_spin.setSingleStep(100)
        self.delay_spin.setValue(config.request_delay_ms)
        self.delay_spin.setSuffix(" ms between batches")
        form.addRow("Rate-limit delay:", self.delay_spin)

        hint = QLabel(
            "Retries: up to 3 with exponential backoff (1 s → 2 s → 4 s) on "
            "HTTP 429/5xx/network errors. These settings persist across sessions."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        root.addWidget(hint)

        # --- Reset to defaults + OK/Cancel ---
        btns = QDialogButtonBox(
            QDialogButtonBox.RestoreDefaults
            | QDialogButtonBox.Ok
            | QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self._apply_and_accept)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.RestoreDefaults).clicked.connect(
            self._reset_defaults
        )
        root.addWidget(btns)

    # -- internal ---
    def _toggle_api_visibility(self, shown: bool) -> None:
        self.api_edit.setEchoMode(QLineEdit.Normal if shown else QLineEdit.Password)

    def _reset_defaults(self) -> None:
        defaults = AppConfig()
        self.prompt_edit.setPlainText(defaults.prompt)
        self.target_edit.setText(defaults.target_language)
        self.batch_spin.setValue(DEFAULT_BATCH_SIZE)
        self.delay_spin.setValue(DEFAULT_REQUEST_DELAY_MS)
        if defaults.font_family and self.font_family.findText(defaults.font_family) != -1:
            self.font_family.setCurrentText(defaults.font_family)
        self.font_size.setValue(defaults.font_size_px)

    def _apply_and_accept(self) -> None:
        self._config.api_key = self.api_edit.text().strip()
        self._config.target_language = (
            self.target_edit.text().strip() or "English"
        )
        prompt = self.prompt_edit.toPlainText().strip()
        self._config.prompt = prompt or DEFAULT_PROMPT
        self._config.font_family = (
            self.font_family.currentText().strip() or AppConfig().font_family
        )
        self._config.font_size_px = int(self.font_size.value())
        self._config.batch_size = int(self.batch_spin.value())
        self._config.request_delay_ms = int(self.delay_spin.value())
        self.accept()
