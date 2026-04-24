"""Background QThread workers to keep the UI responsive.

``BatchTranslateWorker`` is the interesting one:

* Groups the incoming cues into chunks of ``batch_size`` and sends
  ONE API request per chunk (using the numbered-batch prompt in
  :mod:`app.gemini_api`).
* Sleeps ``request_delay_ms`` between chunks to stay under Gemini's
  per-minute rate limit. The sleep is interruptible — it checks
  the cancel flag roughly every 100 ms.
* Retries each chunk up to ``max_retries`` times on transient errors
  (HTTP 429 / 5xx / network) with exponential backoff 1 s → 2 s → 4 s.
* Validates the line count returned by the API. If it mismatches the
  number of input lines, the worker marks the short/missing entries
  as failures rather than silently mapping the wrong translations to
  the wrong cues.
"""

from __future__ import annotations

import time
from typing import List, Optional, Tuple

from PyQt5.QtCore import QThread, pyqtSignal

from ..gemini_api import GeminiError, GeminiTransientError, GeminiTranslator


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
    """Translate an ordered list of subtitles in numbered batches.

    Progress is emitted per-cue (not per-batch) so the progress bar
    advances smoothly and the UI can live-update each table row as
    translations come in.
    """

    progress = pyqtSignal(int, int, int, str)  # done, total, entry_index, translated
    failed = pyqtSignal(int, str)              # entry_index, error
    finished_all = pyqtSignal()

    def __init__(
        self,
        translator: GeminiTranslator,
        items: List[Tuple[int, str]],  # [(entry_index, source_text), ...]
        batch_size: int = 40,
        request_delay_ms: int = 1500,
        max_retries: int = 3,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._items = items
        self._batch_size = max(1, int(batch_size))
        self._request_delay_ms = max(0, int(request_delay_ms))
        self._max_retries = max(0, int(max_retries))
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    # -- helpers ---------------------------------------------------
    def _sleep_interruptible(self, ms: int) -> None:
        """Sleep for ``ms`` milliseconds but wake up on cancel."""
        if ms <= 0:
            return
        deadline = time.monotonic() + ms / 1000.0
        while not self._cancel:
            now = time.monotonic()
            if now >= deadline:
                return
            time.sleep(min(0.1, deadline - now))

    def _translate_chunk_with_retries(
        self, chunk: List[Tuple[int, str]]
    ) -> List[str]:
        """Call the batch API for ``chunk`` with exponential backoff.

        Returns the translation list on success. Raises :class:`GeminiError`
        if all retries fail. Does NOT catch ``GeminiError`` — caller
        decides how to surface it.
        """
        sources = [t for _, t in chunk]
        attempt = 0
        last_error: Optional[Exception] = None
        # Attempt 0 is the initial try; subsequent attempts are retries.
        while attempt <= self._max_retries:
            if self._cancel:
                raise GeminiError("cancelled")
            try:
                return self._translator.translate_batch_numbered(sources)
            except GeminiTransientError as e:
                last_error = e
                if attempt >= self._max_retries:
                    break
                # Exponential backoff: 1 s, 2 s, 4 s, ...
                backoff_ms = int(1000 * (2 ** attempt))
                self._sleep_interruptible(backoff_ms)
                attempt += 1
                continue
            except GeminiError:
                # Non-transient (bad key, malformed response, etc.) — do not retry.
                raise
        # All retries exhausted on transient errors.
        raise GeminiError(
            f"Batch failed after {self._max_retries + 1} attempts: {last_error}"
        )

    # -- main loop -------------------------------------------------
    def run(self) -> None:  # noqa: D401
        total = len(self._items)
        done = 0
        # Chunk deterministically so the order of the input is preserved.
        for start in range(0, total, self._batch_size):
            if self._cancel:
                break
            chunk = self._items[start : start + self._batch_size]

            try:
                translations = self._translate_chunk_with_retries(chunk)
            except GeminiError as e:
                # Report every cue in this chunk as failed so the user
                # sees the full scope of the problem (and so the caller's
                # fail counter reflects reality).
                msg = str(e)
                for entry_index, _ in chunk:
                    if self._cancel:
                        break
                    self.failed.emit(entry_index, msg)
                    done += 1
                # Rate-limit before the next chunk even after a failure —
                # hammering the API immediately after a 429 guarantees
                # another 429.
                self._sleep_interruptible(self._request_delay_ms)
                continue
            except Exception as e:  # pragma: no cover - defensive
                for entry_index, _ in chunk:
                    self.failed.emit(entry_index, f"Unexpected: {e}")
                    done += 1
                self._sleep_interruptible(self._request_delay_ms)
                continue

            # Validate length — if the API dropped lines the parser
            # pads with "" and we flag those specific cues as failed
            # so they can be retried individually later.
            if len(translations) != len(chunk):
                # Defensive; parse_numbered_response already guarantees
                # exact length, but be explicit.
                msg = (
                    f"Line-count mismatch (expected {len(chunk)}, "
                    f"got {len(translations)})"
                )
                for entry_index, _ in chunk:
                    self.failed.emit(entry_index, msg)
                    done += 1
                self._sleep_interruptible(self._request_delay_ms)
                continue

            for (entry_index, _), translated in zip(chunk, translations):
                if self._cancel:
                    break
                done += 1
                if not translated.strip():
                    # The model either returned nothing for this line or
                    # the parser couldn't recover it. Report as a failure
                    # so the user knows to retry that specific cue.
                    self.failed.emit(
                        entry_index,
                        "Empty translation returned for this line",
                    )
                    continue
                self.progress.emit(done, total, entry_index, translated)

            # Inter-chunk rate-limit cooldown.
            self._sleep_interruptible(self._request_delay_ms)

        # Don't signal completion if we were cancelled — the caller has
        # already torn down the worker in its cancel branch, and a late
        # ``finished_all`` could otherwise null out a subsequently-started
        # batch worker via ``_on_batch_done``.
        if not self._cancel:
            self.finished_all.emit()
