"""Main application window.

Layout:

    +-------------------------------------------------+
    |                 VIDEO AREA                      |
    |   (libvlc attached; subtitle overlay on top)    |
    +-------------------------------------------------+
    |  [Play] [seek slider ...............] 00:00/00:00|
    +------------------------+------------------------+
    |  Subtitle list         |  Editor & translate    |
    |  (start | end | text)  |  [text box]            |
    |                        |  [Translate] [Apply]   |
    +------------------------+------------------------+
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from PyQt5.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QShortcut,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig
from ..gemini_api import GeminiTranslator
from ..subtitle_parser import SubtitleDocument, SubtitleEntry, format_ms
from ..video_player import VideoPlayer
from .settings_dialog import SettingsDialog
from .styles import DARK_QSS
from .workers import BatchTranslateWorker, TranslateWorker


# Poll the VLC clock at ~10Hz — fast enough to feel in-sync, light on CPU.
SYNC_INTERVAL_MS = 100


class VideoFrame(QFrame):
    """Black frame that hosts the libvlc output + a subtitle overlay.

    The overlay is **not** a child of this frame. On Linux/X11 libvlc
    draws into this widget's native X window with a separate output
    thread, so any QWidget children of ``VideoFrame`` end up silently
    clipped or redrawn under the libvlc surface.

    To dodge that we keep the overlay as a **frameless top-level
    tool window** and reposition it ourselves (anchored to the bottom-
    centre of this frame in screen coordinates). This makes the overlay
    an independent X window that sits above libvlc's output in the
    stacking order, which is exactly what we need.
    """

    double_clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("VideoArea")
        self.setStyleSheet(
            "QFrame#VideoArea { background-color: #000; border-radius: 8px; }"
        )
        self.setAttribute(Qt.WA_NativeWindow, True)
        self.setAttribute(Qt.WA_DontCreateNativeAncestors, True)
        self.setAutoFillBackground(True)
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Top-level frameless overlay — parent=None so it is its own
        # native window and thus stacks above libvlc's video output.
        self.overlay = QLabel(None)
        self.overlay.setObjectName("SubtitleOverlay")
        self.overlay.setAlignment(Qt.AlignCenter)
        self.overlay.setWordWrap(True)
        self.overlay.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
            | Qt.NoDropShadowWindowHint
        )
        self.overlay.setAttribute(Qt.WA_TranslucentBackground, True)
        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.overlay.setAttribute(Qt.WA_ShowWithoutActivating, True)
        # Default overlay style; re-applied with user-chosen font/size
        # via :meth:`apply_overlay_font` when settings change.
        self._overlay_font_family = "Sans Serif"
        self._overlay_font_size_px = 20
        self._apply_overlay_stylesheet()
        self.overlay.hide()

    def _apply_overlay_stylesheet(self) -> None:
        # Top-level widgets don't inherit the main window's stylesheet,
        # so style the overlay directly.
        self.overlay.setStyleSheet(
            "QLabel {"
            f" color: #FFFFFF;"
            f" background-color: rgba(0, 0, 0, 180);"
            f" border-radius: 6px;"
            f" padding: 6px 14px;"
            f" font-family: \"{self._overlay_font_family}\";"
            f" font-size: {self._overlay_font_size_px}px;"
            f" font-weight: 500;"
            "}"
        )

    def apply_overlay_font(self, family: str, size_px: int) -> None:
        self._overlay_font_family = family or "Sans Serif"
        self._overlay_font_size_px = max(8, min(72, int(size_px)))
        self._apply_overlay_stylesheet()
        # Recompute geometry so the new font size gets the right width.
        self.overlay.adjustSize()
        self._reposition_overlay()

    def set_subtitle(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            self.overlay.hide()
            return
        # Enforce a max of 2 visible lines by hard-wrapping very long lines.
        lines = text.splitlines()
        if len(lines) > 2:
            lines = [lines[0], " ".join(lines[1:])]
        self.overlay.setText("\n".join(lines))
        self._reposition_overlay()
        if not self.overlay.isVisible():
            self.overlay.show()
        self.overlay.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._reposition_overlay()

    def moveEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().moveEvent(event)
        self._reposition_overlay()

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt override
        # Keep the overlay from floating over other apps when this frame
        # is hidden (e.g. app minimised). The overlay is a separate
        # top-level QLabel — it may already have been closed/deleted
        # during shutdown, so tolerate that race.
        try:
            self.overlay.hide()
        except RuntimeError:
            pass
        super().hideEvent(event)

    def _reposition_overlay(self) -> None:
        if not self.overlay.text():
            return
        # Compute the anchor in global screen coordinates so the overlay
        # follows the frame through window drags, splitter resizes, and
        # maximise/restore.
        if not self.isVisible():
            return
        max_width = max(200, int(self.width() * 0.85))
        self.overlay.setMaximumWidth(max_width)
        self.overlay.adjustSize()
        top_left = self.mapToGlobal(QPoint(0, 0))
        x = top_left.x() + (self.width() - self.overlay.width()) // 2
        y = top_left.y() + self.height() - self.overlay.height() - 24
        self.overlay.move(max(0, x), max(0, y))

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


class SubtitleTable(QTableWidget):
    """Three-column table: start | end | text."""

    jump_to_entry = pyqtSignal(int)  # entry_index (1-based)

    COLS = ("Start", "End", "Subtitle")

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(0, 3, parent)
        self.setHorizontalHeaderLabels(self.COLS)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setWordWrap(True)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.verticalHeader().setDefaultSectionSize(32)
        self.doubleClicked.connect(self._on_double_clicked)

    def load(self, entries: List[SubtitleEntry]) -> None:
        self.setRowCount(0)
        self.setRowCount(len(entries))
        for row, e in enumerate(entries):
            start = QTableWidgetItem(format_ms(e.start_ms))
            end = QTableWidgetItem(format_ms(e.end_ms))
            text = QTableWidgetItem(e.display_text)
            for it in (start, end):
                it.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            # Store 1-based entry index on the row.
            start.setData(Qt.UserRole, e.index)
            self.setItem(row, 0, start)
            self.setItem(row, 1, end)
            self.setItem(row, 2, text)

    def update_row(self, row: int, entry: SubtitleEntry) -> None:
        if 0 <= row < self.rowCount():
            self.item(row, 0).setText(format_ms(entry.start_ms))
            self.item(row, 1).setText(format_ms(entry.end_ms))
            self.item(row, 2).setText(entry.display_text)

    def select_row(self, row: int) -> None:
        if 0 <= row < self.rowCount() and row != self.currentRow():
            self.selectRow(row)
            self.scrollToItem(
                self.item(row, 0),
                QAbstractItemView.PositionAtCenter,
            )

    def _on_double_clicked(self, index) -> None:
        row = index.row()
        if row < 0:
            return
        item = self.item(row, 0)
        if item is None:
            return
        entry_index = item.data(Qt.UserRole)
        if entry_index is not None:
            self.jump_to_entry.emit(int(entry_index))


class MainWindow(QMainWindow):
    """Top-level window wiring all components together."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Subtitle Translator — AI-Powered")
        self.resize(1280, 820)
        self.setStyleSheet(DARK_QSS)

        # --- State ---
        self.document = SubtitleDocument()
        self.current_row: int = -1
        self._last_delay_ms: int = 0
        self._active_workers: List[TranslateWorker] = []
        self._batch_worker: Optional[BatchTranslateWorker] = None
        # Per-batch failure tally. We deliberately do NOT pop a modal
        # dialog per failure here — with a bad API key that would flood
        # the UI with one blocking ``QMessageBox`` per cue, locking the
        # Cancel button behind a queue of nested event loops. Instead
        # we accumulate and show a single summary in ``_on_batch_done``.
        self._batch_fail_count: int = 0
        self._batch_first_error: Optional[str] = None
        # Set to True when the app minimises; we use it to gate the
        # sync tick so no overlay / status updates fire while hidden.
        self._minimised = False
        self._was_playing_before_minimise = False

        # --- Persistent user config ---
        self.config = AppConfig.load()

        # --- Video engine ---
        try:
            self.player = VideoPlayer()
        except RuntimeError as e:
            QMessageBox.critical(self, "VLC not available", str(e))
            raise

        # Translator holds a reference to the live config so changes
        # made via the Settings dialog (API key, prompt, language) take
        # effect immediately without reconstructing the worker.
        self.translator = GeminiTranslator(self.config)

        # --- Widgets ---
        self._build_toolbar()
        self._build_central()
        self._build_status_bar()
        self._build_shortcuts()

        # Attach libvlc output *after* the window is shown so winId() is valid.
        QTimer.singleShot(0, self._attach_player)

        # Apply persisted font settings to the overlay once widgets exist.
        self.video_frame.apply_overlay_font(
            self.config.font_family, self.config.font_size_px
        )

        # Sync timer: drives subtitle overlay + seek bar.
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(SYNC_INTERVAL_MS)
        self._sync_timer.timeout.connect(self._on_tick)
        self._sync_timer.start()

    # ---------------------------------------------------------------
    # Construction
    # ---------------------------------------------------------------
    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(tb.iconSize())
        self.addToolBar(tb)

        open_video_btn = QPushButton("Open Video…")
        open_video_btn.clicked.connect(self.open_video)
        tb.addWidget(open_video_btn)

        open_srt_btn = QPushButton("Open SRT…")
        open_srt_btn.clicked.connect(self.open_srt)
        tb.addWidget(open_srt_btn)

        tb.addSeparator()

        self.batch_btn = QPushButton("Translate All")
        self.batch_btn.clicked.connect(self.translate_all)
        tb.addWidget(self.batch_btn)

        self.save_btn = QPushButton("Export SRT…")
        self.save_btn.clicked.connect(self.export_srt)
        tb.addWidget(self.save_btn)

        tb.addSeparator()

        tb.addWidget(QLabel("Delay (ms):"))
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(-600000, 600000)
        self.delay_spin.setSingleStep(100)
        self.delay_spin.setValue(0)
        self.delay_spin.setToolTip("Shift all subtitles (positive = later).")
        self.delay_spin.valueChanged.connect(self._on_delay_changed)
        tb.addWidget(self.delay_spin)

        # Spacer pushes Settings to the far right of the toolbar.
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        self.settings_btn = QPushButton("Settings…")
        self.settings_btn.clicked.connect(self.open_settings)
        tb.addWidget(self.settings_btn)

    def _build_central(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(10)

        # Video card
        video_card = QFrame()
        video_card.setObjectName("Card")
        v_layout = QVBoxLayout(video_card)
        v_layout.setContentsMargins(12, 12, 12, 12)
        v_layout.setSpacing(10)

        self.video_frame = VideoFrame()
        self.video_frame.double_clicked.connect(self.toggle_play)
        v_layout.addWidget(self.video_frame, 1)

        # Transport controls
        transport = QHBoxLayout()
        transport.setSpacing(10)
        self.play_btn = QPushButton("Play")
        self.play_btn.setObjectName("Primary")
        self.play_btn.clicked.connect(self.toggle_play)
        transport.addWidget(self.play_btn)

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.sliderMoved.connect(self._on_slider_moved)
        self.seek_slider.sliderReleased.connect(self._on_slider_released)
        self._user_scrubbing = False
        transport.addWidget(self.seek_slider, 1)

        self.time_label = QLabel("00:00:00.000 / 00:00:00.000")
        self.time_label.setObjectName("TimeLabel")
        transport.addWidget(self.time_label)

        v_layout.addLayout(transport)
        outer.addWidget(video_card, 3)

        # Lower split: table | editor
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)

        # Left: subtitle list
        list_card = QFrame()
        list_card.setObjectName("Card")
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(12, 12, 12, 12)
        list_layout.setSpacing(8)
        title = QLabel("Subtitles")
        title.setObjectName("HeaderTitle")
        list_layout.addWidget(title)
        self.table = SubtitleTable()
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.jump_to_entry.connect(self._jump_to_entry_index)
        list_layout.addWidget(self.table, 1)
        splitter.addWidget(list_card)

        # Right: editor
        edit_card = QFrame()
        edit_card.setObjectName("Card")
        edit_layout = QVBoxLayout(edit_card)
        edit_layout.setContentsMargins(12, 12, 12, 12)
        edit_layout.setSpacing(8)

        edit_header = QHBoxLayout()
        edit_title = QLabel("Editor")
        edit_title.setObjectName("HeaderTitle")
        edit_header.addWidget(edit_title)
        edit_header.addStretch(1)
        self.entry_time_label = QLabel("—")
        self.entry_time_label.setObjectName("TimeLabel")
        edit_header.addWidget(self.entry_time_label)
        edit_layout.addLayout(edit_header)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            "Select a subtitle from the list to edit it.\n"
            "Press Enter (Ctrl+Enter inside the box) to apply changes."
        )
        edit_layout.addWidget(self.editor, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.translate_btn = QPushButton("Translate")
        self.translate_btn.clicked.connect(self.translate_current)
        btn_row.addWidget(self.translate_btn)

        self.revert_btn = QPushButton("Revert to Original")
        self.revert_btn.clicked.connect(self.revert_current)
        btn_row.addWidget(self.revert_btn)

        btn_row.addStretch(1)

        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.setObjectName("Primary")
        self.apply_btn.clicked.connect(self.apply_current)
        btn_row.addWidget(self.apply_btn)
        edit_layout.addLayout(btn_row)

        splitter.addWidget(edit_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter, 4)

        self._set_editor_enabled(False)
        self.setCentralWidget(root)

    def _build_status_bar(self) -> None:
        bar = QStatusBar()
        self.setStatusBar(bar)
        self.status_msg = QLabel("Ready")
        self.status_msg.setObjectName("Muted")
        bar.addWidget(self.status_msg, 1)

        self.progress = QProgressBar()
        self.progress.setMaximumWidth(220)
        self.progress.setVisible(False)
        bar.addPermanentWidget(self.progress)

    def _build_shortcuts(self) -> None:
        # Space: play/pause globally (except when typing).
        space = QShortcut(QKeySequence(Qt.Key_Space), self)
        space.setContext(Qt.WindowShortcut)
        space.activated.connect(self._space_pressed)

        # Ctrl+Enter: apply changes from inside the editor.
        apply_sc = QShortcut(QKeySequence("Ctrl+Return"), self)
        apply_sc.activated.connect(self.apply_current)
        apply_sc2 = QShortcut(QKeySequence("Ctrl+Enter"), self)
        apply_sc2.activated.connect(self.apply_current)

        # Ctrl+S: export.
        save_sc = QShortcut(QKeySequence.Save, self)
        save_sc.activated.connect(self.export_srt)

    def _attach_player(self) -> None:
        try:
            self.player.attach_to_widget(self.video_frame)
        except Exception as e:  # pragma: no cover
            self._set_status(f"Failed to attach VLC: {e}")

    # ---------------------------------------------------------------
    # File I/O
    # ---------------------------------------------------------------
    def open_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            "",
            "Video files (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv);;All files (*)",
        )
        if not path:
            return
        try:
            self.player.load(path)
            self.player.play()
            self.play_btn.setText("Pause")
            self._set_status(f"Loaded video: {Path(path).name}")
        except Exception as e:
            QMessageBox.warning(self, "Video error", str(e))

    def open_srt(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open SRT subtitle", "", "SubRip (*.srt);;All files (*)"
        )
        if not path:
            return
        try:
            new_doc = SubtitleDocument.from_file(path)
        except Exception as e:
            QMessageBox.warning(self, "Subtitle error", str(e))
            return

        # Cancel any in-flight translation work so stale entry indices from
        # the previous document don't bleed into the new one.
        self._cancel_all_translation_work()

        self.document = new_doc
        self.current_row = -1

        # Reset the delay spinner so the delta-based delay logic starts
        # from zero for the freshly-loaded document.
        self._last_delay_ms = 0
        self.delay_spin.blockSignals(True)
        self.delay_spin.setValue(0)
        self.delay_spin.blockSignals(False)

        self.table.load(self.document.entries)
        self._set_status(
            f"Loaded {len(self.document)} subtitles from {Path(path).name}"
        )
        if self.document.entries:
            self.table.select_row(0)

    def export_srt(self) -> None:
        if not self.document.entries:
            return
        default = "translated.srt"
        if self.document.source_path is not None:
            p = self.document.source_path
            default = str(p.with_name(p.stem + ".translated.srt"))
        path, _ = QFileDialog.getSaveFileName(
            self, "Export SRT", default, "SubRip (*.srt)"
        )
        if not path:
            return
        try:
            self.document.save(path, use_translated=True)
            self._set_status(f"Saved {path}")
        except Exception as e:
            QMessageBox.warning(self, "Save error", str(e))

    # ---------------------------------------------------------------
    # Transport & sync
    # ---------------------------------------------------------------
    def toggle_play(self) -> None:
        self.player.toggle()
        self.play_btn.setText("Pause" if self.player.is_playing() else "Play")

    def _space_pressed(self) -> None:
        # Don't hijack Space when typing in the editor.
        focus = QApplication.focusWidget()
        if isinstance(focus, (QPlainTextEdit,)):
            return
        self.toggle_play()

    def _on_tick(self) -> None:
        # Defensive: if the timer somehow fires while minimised (race
        # between ``stop()`` and a queued timeout), do nothing. The
        # overlay is hidden and we don't want to re-show it.
        if self._minimised:
            return
        pos = self.player.position_ms()
        dur = self.player.duration_ms()

        # Seek slider update (skip while user is dragging).
        if dur > 0:
            if self.seek_slider.maximum() != dur:
                self.seek_slider.setRange(0, dur)
            if not self._user_scrubbing:
                self.seek_slider.setValue(pos)
        self.time_label.setText(f"{format_ms(pos)} / {format_ms(dur)}")

        # Subtitle overlay + list auto-scroll.
        entry = self.document.entry_at(pos)
        self.video_frame.set_subtitle(entry.display_text if entry else "")
        # Re-anchor each tick so the top-level overlay tracks window
        # drags, splitter resizes, and maximise/restore transitions —
        # Qt doesn't deliver moveEvent to child widgets when the
        # top-level window moves, so we reposition unconditionally.
        self.video_frame._reposition_overlay()
        if entry is not None:
            row = entry.index - 1
            if row != self.current_row:
                # Block signal emission so we don't toggle the editor text.
                self.table.blockSignals(True)
                self.table.select_row(row)
                self.table.blockSignals(False)
                self._load_entry_into_editor(row)

        # Keep play/pause label accurate when media ends.
        self.play_btn.setText("Pause" if self.player.is_playing() else "Play")

    def _on_slider_moved(self, value: int) -> None:
        self._user_scrubbing = True
        self.time_label.setText(
            f"{format_ms(value)} / {format_ms(self.player.duration_ms())}"
        )

    def _on_slider_released(self) -> None:
        self.player.seek_ms(self.seek_slider.value())
        self._user_scrubbing = False

    def _jump_to_entry_index(self, entry_index: int) -> None:
        row = entry_index - 1
        if 0 <= row < len(self.document):
            entry = self.document.entries[row]
            self.player.seek_ms(entry.start_ms)
            self.player.play()
            self.play_btn.setText("Pause")

    # ---------------------------------------------------------------
    # Editor
    # ---------------------------------------------------------------
    def _set_editor_enabled(self, enabled: bool) -> None:
        for w in (
            self.editor,
            self.translate_btn,
            self.revert_btn,
            self.apply_btn,
        ):
            w.setEnabled(enabled)

    def _on_selection_changed(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.document):
            self.current_row = -1
            self._set_editor_enabled(False)
            self.editor.clear()
            self.entry_time_label.setText("—")
            return
        self.current_row = row
        self._load_entry_into_editor(row)
        self._set_editor_enabled(True)

    def _load_entry_into_editor(self, row: int) -> None:
        if row < 0 or row >= len(self.document):
            return
        self.current_row = row
        entry = self.document.entries[row]
        # Only overwrite the editor if focus is elsewhere so we don't stomp
        # on the user's in-progress typing when auto-advancing during playback.
        if QApplication.focusWidget() is not self.editor:
            self.editor.setPlainText(entry.display_text)
        self.entry_time_label.setText(
            f"{format_ms(entry.start_ms)} → {format_ms(entry.end_ms)}"
        )

    def apply_current(self) -> None:
        if self.current_row < 0:
            return
        entry = self.document.entries[self.current_row]
        new_text = self.editor.toPlainText().strip()
        # Apply to the translated field so the original is retained.
        entry.translated = new_text if new_text != entry.text else None
        self.table.update_row(self.current_row, entry)
        # Refresh overlay if this cue is currently on screen.
        pos = self.player.position_ms()
        if entry.contains(pos):
            self.video_frame.set_subtitle(entry.display_text)
        self._set_status(f"Applied changes to #{entry.index}")

    def revert_current(self) -> None:
        if self.current_row < 0:
            return
        entry = self.document.entries[self.current_row]
        entry.translated = None
        self.editor.setPlainText(entry.text)
        self.table.update_row(self.current_row, entry)
        self._set_status(f"Reverted #{entry.index} to original")

    # ---------------------------------------------------------------
    # Translation
    # ---------------------------------------------------------------
    def _prune_workers(self) -> None:
        self._active_workers = [w for w in self._active_workers if w.isRunning()]

    def _cancel_all_translation_work(self) -> None:
        """Stop any in-flight single/batch translations.

        Called when swapping documents so stale ``entry_index`` values from
        the previous document cannot leak into the new one via signals.
        """
        if self._batch_worker is not None and self._batch_worker.isRunning():
            self._batch_worker.cancel()
            # Short, bounded wait; the worker only polls ``_cancel`` between
            # HTTP calls so we can't guarantee instant termination.
            self._batch_worker.wait(1500)
        # Disconnect stale signals regardless of whether the worker stopped.
        if self._batch_worker is not None:
            try:
                self._batch_worker.progress.disconnect()
                self._batch_worker.failed.disconnect()
                self._batch_worker.finished_all.disconnect()
            except TypeError:
                pass
        self._batch_worker = None

        for w in self._active_workers:
            try:
                w.finished_ok.disconnect()
                w.failed.disconnect()
            except TypeError:
                pass
            if w.isRunning():
                w.wait(500)
        self._active_workers.clear()

        # Restore UI affordances to their idle state.
        self.progress.setVisible(False)
        self.batch_btn.setText("Translate All")
        self.translate_btn.setEnabled(True)

    def translate_current(self) -> None:
        if self.current_row < 0:
            return
        entry = self.document.entries[self.current_row]
        source_text = entry.text
        if not source_text.strip():
            return
        # Provide a bit of surrounding context to improve translation quality.
        ctx_parts: List[str] = []
        for off in (-2, -1, 1, 2):
            j = self.current_row + off
            if 0 <= j < len(self.document):
                ctx_parts.append(self.document.entries[j].text)
        context = "\n".join(ctx_parts) if ctx_parts else None

        self.translate_btn.setEnabled(False)
        self._set_status(f"Translating #{entry.index}…")
        worker = TranslateWorker(self.translator, entry.index, source_text, context, self)
        worker.finished_ok.connect(self._on_translate_ok)
        worker.failed.connect(self._on_translate_fail)
        worker.finished.connect(self._prune_workers)
        worker.finished.connect(lambda: self.translate_btn.setEnabled(True))
        self._active_workers.append(worker)
        worker.start()

    def _on_translate_ok(self, entry_index: int, text: str) -> None:
        row = entry_index - 1
        if 0 <= row < len(self.document):
            self.document.entries[row].translated = text
            self.table.update_row(row, self.document.entries[row])
            if row == self.current_row:
                self.editor.setPlainText(text)
            self._set_status(f"Translated #{entry_index}")

    def _on_translate_fail(self, entry_index: int, msg: str) -> None:
        self._set_status(f"Translation failed (#{entry_index}): {msg}")
        QMessageBox.warning(self, "Translation failed", msg)

    def translate_all(self) -> None:
        if not self.document.entries:
            return
        if self._batch_worker is not None and self._batch_worker.isRunning():
            # Cancel the ongoing batch and sever its signal connections so
            # a late-arriving `finished_all` from the cancelled worker
            # can't null out a subsequently-started batch worker.
            self._batch_worker.cancel()
            try:
                self._batch_worker.progress.disconnect()
                self._batch_worker.failed.disconnect()
                self._batch_worker.finished_all.disconnect()
            except TypeError:
                pass
            self._batch_worker = None
            self.progress.setVisible(False)
            self.batch_btn.setText("Translate All")
            self._set_status("Batch translation cancelled")
            return
        if not self.config.resolved_api_key():
            QMessageBox.warning(
                self,
                "Missing API key",
                "Gemini API key is not configured.\n\n"
                "Open Settings… to paste your key, or export "
                "GEMINI_API_KEY in your environment.",
            )
            return

        # Skip empty cues up front so the API never receives them.
        items: List[Tuple[int, str]] = [
            (e.index, e.text) for e in self.document.entries if e.text.strip()
        ]
        if not items:
            return
        self.progress.setRange(0, len(items))
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.batch_btn.setText("Cancel")
        self._set_status(
            f"Batch translating {len(items)} subtitles "
            f"(batch size {self.config.batch_size}, "
            f"delay {self.config.request_delay_ms} ms)…"
        )
        # Reset the per-batch failure tally before starting.
        self._batch_fail_count = 0
        self._batch_first_error = None

        worker = BatchTranslateWorker(
            self.translator,
            items,
            batch_size=self.config.batch_size,
            request_delay_ms=self.config.request_delay_ms,
            parent=self,
        )
        worker.progress.connect(self._on_batch_progress)
        # Route batch failures to a non-modal aggregator; ``_on_translate_fail``
        # (used for single-cue translations) pops a dialog per failure and
        # would flood the UI here.
        worker.failed.connect(self._on_batch_translate_fail)
        worker.finished_all.connect(self._on_batch_done)
        self._batch_worker = worker
        worker.start()

    def _on_batch_progress(
        self, done: int, total: int, entry_index: int, translated: str
    ) -> None:
        row = entry_index - 1
        if 0 <= row < len(self.document):
            self.document.entries[row].translated = translated
            self.table.update_row(row, self.document.entries[row])
            if row == self.current_row:
                self.editor.setPlainText(translated)
        self.progress.setValue(done)
        self._set_status(f"Translated {done}/{total}")

    def _on_batch_translate_fail(self, entry_index: int, msg: str) -> None:
        """Silently tally batch failures; summary is shown in ``_on_batch_done``.

        We deliberately do NOT show a modal dialog here — during a broken
        run (e.g. invalid API key) every item fails, and popping one modal
        per cue would block the user from even reaching the Cancel button.
        """
        self._batch_fail_count += 1
        if self._batch_first_error is None:
            self._batch_first_error = msg
        self._set_status(
            f"Batch translation: {self._batch_fail_count} failure(s) so far"
        )

    def _on_batch_done(self) -> None:
        self.progress.setVisible(False)
        self.batch_btn.setText("Translate All")
        self._batch_worker = None
        if self._batch_fail_count:
            sample = self._batch_first_error or ""
            self._set_status(
                f"Batch translation finished with {self._batch_fail_count} failure(s)"
            )
            QMessageBox.warning(
                self,
                "Batch translation finished with errors",
                f"{self._batch_fail_count} subtitle(s) failed to translate.\n\n"
                f"First error:\n{sample}",
            )
        else:
            self._set_status("Batch translation finished")
        # Clear the tally regardless so the next batch starts fresh.
        self._batch_fail_count = 0
        self._batch_first_error = None

    # ---------------------------------------------------------------
    # Misc
    # ---------------------------------------------------------------
    def _on_delay_changed(self, value_ms: int) -> None:
        # Absolute apply: each cue = original + value_ms. This is lossless
        # across repeated negative-then-positive sweeps (no delta drift).
        if not self.document.entries:
            self._last_delay_ms = value_ms
            return
        self.document.apply_delay(value_ms)
        self._last_delay_ms = value_ms
        for row, e in enumerate(self.document.entries):
            self.table.update_row(row, e)
        self._set_status(f"Delay set to {value_ms:+d} ms")

    def _set_status(self, text: str) -> None:
        self.status_msg.setText(text)

    # ---------------------------------------------------------------
    # Settings
    # ---------------------------------------------------------------
    def open_settings(self) -> None:
        dlg = SettingsDialog(self.config, self)
        if dlg.exec_() != SettingsDialog.Accepted:
            return
        try:
            saved_at = self.config.save()
            self._set_status(f"Settings saved to {saved_at}")
        except OSError as e:
            QMessageBox.warning(
                self,
                "Could not save settings",
                f"Failed to write config file:\n{e}",
            )
        # Apply any runtime-visible changes immediately.
        self.video_frame.apply_overlay_font(
            self.config.font_family, self.config.font_size_px
        )

    # ---------------------------------------------------------------
    # Window-state transitions (minimise / restore)
    # ---------------------------------------------------------------
    def changeEvent(self, event) -> None:  # noqa: N802 - Qt override
        # ``WindowStateChange`` fires when the window is minimised,
        # restored, maximised, etc. We only treat minimise specially:
        # hide the top-level overlay so it can't float over other apps
        # as a ghost, pause playback, and stop the sync timer so no
        # background signals fire on an invisible UI.
        from PyQt5.QtCore import QEvent  # local import keeps Qt out of module scope
        if event.type() == QEvent.WindowStateChange:
            is_min = bool(self.windowState() & Qt.WindowMinimized)
            if is_min and not self._minimised:
                self._enter_minimised()
            elif not is_min and self._minimised:
                self._exit_minimised()
        super().changeEvent(event)

    def _enter_minimised(self) -> None:
        self._minimised = True
        # Stop the subtitle/seek tick so we don't pointlessly repaint.
        if self._sync_timer.isActive():
            self._sync_timer.stop()
        # Hide overlay immediately — it's its own top-level window
        # and would otherwise linger on-screen after minimise.
        self.video_frame.overlay.hide()
        # Pause playback and remember prior state so we can resume it
        # on restore.
        try:
            self._was_playing_before_minimise = self.player.is_playing()
            if self._was_playing_before_minimise:
                self.player.pause()
                self.play_btn.setText("Play")
        except Exception:
            self._was_playing_before_minimise = False

    def _exit_minimised(self) -> None:
        self._minimised = False
        # Resume tick before anything else so the overlay / seek bar
        # catch up on the next interval.
        if not self._sync_timer.isActive():
            self._sync_timer.start()
        if self._was_playing_before_minimise:
            try:
                self.player.play()
                self.play_btn.setText("Pause")
            except Exception:
                pass
        self._was_playing_before_minimise = False

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        try:
            # Top-level overlay is its own window — close it explicitly
            # or it will linger as an orphaned native window.
            self.video_frame.overlay.close()
            if self._batch_worker is not None:
                self._batch_worker.cancel()
                self._batch_worker.wait(1500)
            for w in self._active_workers:
                w.wait(500)
            self.player.release()
        finally:
            super().closeEvent(event)
