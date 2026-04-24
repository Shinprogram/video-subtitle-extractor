"""Background QThread workers to keep the UI responsive.

Using ``QThread`` with signals is the idiomatic Qt way to do async work
without blocking the event loop. We use it for Gemini translation calls
which can take several seconds.
"""

from __future__ import annotations

from typing import List, Optional

from PyQt5.QtCore import QThread, pyqtSignal

from ..gemini_api import GeminiError, GeminiTranslator


class TranslateWorker(QThread):
    """Translate a single subtitle entry in the background."""

    finished_ok = pyqtSignal(int, str)  # entry_index, translated_text
    failed = pyqtSignal(int, str)       # entry_index, error message

    def __init__(
        self,
        translator: GeminiTranslator,
        entry_index: int,
        text: str,
        context: Optional[str] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._entry_index = entry_index
        self._text = text
        self._context = context

    def run(self) -> None:  # noqa: D401 - Qt override
        try:
            result = self._translator.translate(self._text, self._context)
            self.finished_ok.emit(self._entry_index, result)
        except GeminiError as e:
            self.failed.emit(self._entry_index, str(e))
        except Exception as e:  # pragma: no cover - safety net
            self.failed.emit(self._entry_index, f"Unexpected: {e}")


class BatchTranslateWorker(QThread):
    """Translate an ordered list of subtitles."""

    progress = pyqtSignal(int, int, int, str)  # done, total, entry_index, text
    failed = pyqtSignal(int, str)              # entry_index, error
    finished_all = pyqtSignal()

    def __init__(
        self,
        translator: GeminiTranslator,
        items: List[tuple],  # list of (entry_index, source_text)
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._items = items
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:  # noqa: D401
        total = len(self._items)
        for i, (entry_index, text) in enumerate(self._items, start=1):
            if self._cancel:
                break
            try:
                translated = self._translator.translate(text)
                self.progress.emit(i, total, entry_index, translated)
            except GeminiError as e:
                self.failed.emit(entry_index, str(e))
            except Exception as e:  # pragma: no cover
                self.failed.emit(entry_index, f"Unexpected: {e}")
        # Don't signal completion if we were cancelled — the caller has
        # already torn down the worker in its cancel branch, and a late
        # ``finished_all`` could otherwise null out a subsequently-started
        # batch worker via ``_on_batch_done``.
        if not self._cancel:
            self.finished_all.emit()
