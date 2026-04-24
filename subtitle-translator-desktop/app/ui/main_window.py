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

import os
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
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

from ..gemini_api import GeminiTranslator
from ..subtitle_parser import SubtitleDocument, SubtitleEntry, format_ms
from ..video_player import VideoPlayer
from .styles import DARK_QSS
from .workers import BatchTranslateWorker, TranslateWorker


# Poll the VLC clock at ~10Hz — fast enough to feel in-sync, light on CPU.
SYNC_INTERVAL_MS = 100


class VideoFrame(QFrame):
    """Black frame that hosts the libvlc output + a subtitle overlay.

    Using a subclass keeps ``winId()`` stable and lets us anchor the
    overlay label to the bottom-centre via a manual layout on resize.
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

        self.overlay = QLabel("", self)
        self.overlay.setObjectName("SubtitleOverlay")
        self.overlay.setAlignment(Qt.AlignCenter)
        self.overlay.setWordWrap(True)
        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.overlay.hide()

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
        self.overlay.show()
        self.overlay.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._reposition_overlay()

    def _reposition_overlay(self) -> None:
        if not self.overlay.isVisible() and not self.overlay.text():
            return
        max_width = max(200, int(self.width() * 0.85))
        self.overlay.setMaximumWidth(max_width)
        self.overlay.adjustSize()
        x = (self.width() - self.overlay.width()) // 2
        y = self.height() - self.overlay.height() - 24
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

        # --- Video engine ---
        try:
            self.player = VideoPlayer()
        except RuntimeError as e:
            QMessageBox.critical(self, "VLC not available", str(e))
            raise

        self.translator = GeminiTranslator()

        # --- Widgets ---
        self._build_toolbar()
        self._build_central()
        self._build_status_bar()
        self._build_shortcuts()

        # Attach libvlc output *after* the window is shown so winId() is valid.
        QTimer.singleShot(0, self._attach_player)

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
        if not os.environ.get("GEMINI_API_KEY"):
            QMessageBox.warning(
                self,
                "Missing API key",
                "GEMINI_API_KEY environment variable is not set.",
            )
            return

        items: List[Tuple[int, str]] = [
            (e.index, e.text) for e in self.document.entries if e.text.strip()
        ]
        if not items:
            return
        self.progress.setRange(0, len(items))
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.batch_btn.setText("Cancel")
        self._set_status(f"Batch translating {len(items)} subtitles…")

        worker = BatchTranslateWorker(self.translator, items, self)
        worker.progress.connect(self._on_batch_progress)
        worker.failed.connect(self._on_translate_fail)
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

    def _on_batch_done(self) -> None:
        self.progress.setVisible(False)
        self.batch_btn.setText("Translate All")
        self._batch_worker = None
        self._set_status("Batch translation finished")

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

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        try:
            if self._batch_worker is not None:
                self._batch_worker.cancel()
                self._batch_worker.wait(1500)
            for w in self._active_workers:
                w.wait(500)
            self.player.release()
        finally:
            super().closeEvent(event)
