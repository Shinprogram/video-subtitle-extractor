"""SRT subtitle parser and serializer.

Parses .srt files into a list of :class:`SubtitleEntry` objects and
writes them back out preserving the standard SRT format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional


_TIME_RE = re.compile(
    r"(?P<h>\d+):(?P<m>\d{1,2}):(?P<s>\d{1,2})[,.](?P<ms>\d{1,3})"
)
_TIMING_LINE_RE = re.compile(
    r"^\s*(?P<start>\d+:\d{1,2}:\d{1,2}[,.]\d{1,3})\s*-->\s*"
    r"(?P<end>\d+:\d{1,2}:\d{1,2}[,.]\d{1,3}).*$"
)


def _timecode_to_ms(tc: str) -> int:
    m = _TIME_RE.match(tc.strip())
    if not m:
        raise ValueError(f"Invalid SRT timecode: {tc!r}")
    h = int(m.group("h"))
    mi = int(m.group("m"))
    s = int(m.group("s"))
    ms = int(m.group("ms").ljust(3, "0"))  # normalize if shorter
    return ((h * 60 + mi) * 60 + s) * 1000 + ms


def _ms_to_timecode(ms: int) -> str:
    if ms < 0:
        ms = 0
    total_seconds, milli = divmod(int(ms), 1000)
    minutes_total, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes_total, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milli:03d}"


@dataclass
class SubtitleEntry:
    """A single subtitle cue.

    Times are stored in milliseconds internally for easy comparison with
    the VLC player's millisecond clock.
    """

    index: int
    start_ms: int
    end_ms: int
    text: str = ""
    # Translated text kept separately so we can toggle/restore it.
    translated: Optional[str] = None
    # Originals captured at parse time so delay shifts can be applied
    # absolutely (from the originals) rather than accumulating deltas
    # through `shift_all`'s max(0, ...) clamp.
    original_start_ms: int = -1
    original_end_ms: int = -1

    def __post_init__(self) -> None:
        if self.original_start_ms < 0:
            self.original_start_ms = self.start_ms
        if self.original_end_ms < 0:
            self.original_end_ms = self.end_ms

    @property
    def display_text(self) -> str:
        """Prefer the translated text when a translation has been set.

        ``translated`` is ``None`` when no override has been applied — we
        must NOT use a truthy check here because an explicitly empty
        string is a valid user edit (e.g. clearing the cue).
        """
        return self.translated if self.translated is not None else self.text

    @property
    def start_tc(self) -> str:
        return _ms_to_timecode(self.start_ms)

    @property
    def end_tc(self) -> str:
        return _ms_to_timecode(self.end_ms)

    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)

    def contains(self, position_ms: int) -> bool:
        return self.start_ms <= position_ms < self.end_ms


@dataclass
class SubtitleDocument:
    """Container for a list of :class:`SubtitleEntry` with utilities."""

    entries: List[SubtitleEntry] = field(default_factory=list)
    source_path: Optional[Path] = None

    # ----- parsing / serialization -----
    @classmethod
    def from_file(cls, path: str | Path) -> "SubtitleDocument":
        p = Path(path)
        # SRT files are usually utf-8 but tolerate BOM / cp1252.
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                text = p.read_text(encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise UnicodeDecodeError(
                "utf-8", b"", 0, 1, f"Could not decode {p}"
            )
        doc = cls.from_string(text)
        doc.source_path = p
        return doc

    @classmethod
    def from_string(cls, text: str) -> "SubtitleDocument":
        # Normalize line endings; split on blank-line boundaries.
        blocks = re.split(r"\r?\n\r?\n+", text.strip("\ufeff\r\n "))
        entries: List[SubtitleEntry] = []
        auto_index = 0
        for raw in blocks:
            if not raw.strip():
                continue
            lines = raw.splitlines()
            # Skip a leading numeric index line if present.
            idx: Optional[int] = None
            timing_line: Optional[str] = None
            body_start = 0
            if lines and lines[0].strip().isdigit():
                try:
                    idx = int(lines[0].strip())
                except ValueError:
                    idx = None
                if len(lines) >= 2 and _TIMING_LINE_RE.match(lines[1]):
                    timing_line = lines[1]
                    body_start = 2
            if timing_line is None and lines and _TIMING_LINE_RE.match(lines[0]):
                timing_line = lines[0]
                body_start = 1
            if timing_line is None:
                # Not a valid cue; skip.
                continue
            m = _TIMING_LINE_RE.match(timing_line)
            if not m:
                continue
            start_ms = _timecode_to_ms(m.group("start"))
            end_ms = _timecode_to_ms(m.group("end"))
            body = "\n".join(lines[body_start:]).strip()
            auto_index += 1
            entries.append(
                SubtitleEntry(
                    index=idx if idx is not None else auto_index,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=body,
                )
            )
        # Sort & re-index to guarantee monotonic ordering.
        entries.sort(key=lambda e: e.start_ms)
        for i, e in enumerate(entries, start=1):
            e.index = i
        return cls(entries=entries)

    def to_srt(self, use_translated: bool = True) -> str:
        parts: List[str] = []
        for i, e in enumerate(self.entries, start=1):
            text = e.display_text if use_translated else e.text
            parts.append(
                f"{i}\n{_ms_to_timecode(e.start_ms)} --> "
                f"{_ms_to_timecode(e.end_ms)}\n{text}\n"
            )
        return "\n".join(parts).strip() + "\n"

    def save(self, path: str | Path, use_translated: bool = True) -> None:
        Path(path).write_text(self.to_srt(use_translated), encoding="utf-8")

    # ----- lookups -----
    def entry_at(self, position_ms: int) -> Optional[SubtitleEntry]:
        """Return the active subtitle at a given millisecond position."""
        # Binary search for efficiency on large SRTs.
        lo, hi = 0, len(self.entries) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            e = self.entries[mid]
            if position_ms < e.start_ms:
                hi = mid - 1
            elif position_ms >= e.end_ms:
                lo = mid + 1
            else:
                return e
        return None

    def shift_all(self, delta_ms: int) -> None:
        """Adjust every cue (and its stored originals) by ``delta_ms``.

        This mutates both the current *and* the original timestamps so
        the shift is idempotent with :meth:`apply_delay`. Most callers
        (the delay spinner) should prefer :meth:`apply_delay`, which is
        absolute and therefore drift-free.
        """
        for e in self.entries:
            e.start_ms = max(0, e.start_ms + delta_ms)
            e.end_ms = max(0, e.end_ms + delta_ms)
            e.original_start_ms = max(0, e.original_start_ms + delta_ms)
            e.original_end_ms = max(0, e.original_end_ms + delta_ms)

    def apply_delay(self, delay_ms: int) -> None:
        """Set each cue's time to ``original + delay_ms`` (clamped >= 0).

        Because we compute against the captured originals rather than
        the current values, repeatedly sweeping the delay through
        negative values is lossless — even for cues near t=0 where a
        naive delta-based approach would silently drift due to clamping.
        """
        for e in self.entries:
            e.start_ms = max(0, e.original_start_ms + delay_ms)
            e.end_ms = max(0, e.original_end_ms + delay_ms)

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self) -> Iterable[SubtitleEntry]:
        return iter(self.entries)


def format_ms(ms: int) -> str:
    """Human-friendly HH:MM:SS.mmm for the UI."""
    return _ms_to_timecode(max(0, int(ms))).replace(",", ".")
