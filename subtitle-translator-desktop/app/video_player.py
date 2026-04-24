"""Thin wrapper around python-vlc for embedding in a Qt widget.

The wrapper hides libvlc details and exposes a small, Qt-friendly API:
``load``, ``play``, ``pause``, ``toggle``, ``seek_ms``, ``position_ms``,
``duration_ms``, ``is_playing`` and ``attach_to_widget``.

We intentionally avoid sub-classing ``QWidget`` here so that the module
stays importable in headless environments (tests / CI) even when Qt is
not installed.
"""

from __future__ import annotations

import sys
from typing import Optional

try:
    import vlc  # type: ignore
except Exception:  # pragma: no cover - import guarded for headless CI
    vlc = None  # type: ignore


class VideoPlayer:
    """Small facade over :mod:`python-vlc`."""

    def __init__(self) -> None:
        if vlc is None:
            raise RuntimeError(
                "python-vlc is not installed; install VLC + `pip install python-vlc`."
            )
        # `--no-xlib` avoids the libvlc X11 lock on Linux; harmless on Windows.
        # `--no-sub-autodetect-file` stops libvlc from silently auto-loading
        # any .srt it finds next to the video and rendering its own subtitle
        # track; we want full control over the Qt overlay so user edits to
        # `SubtitleEntry.translated` are what actually shows on screen.
        args = [
            "--no-video-title-show",
            "--quiet",
            "--no-sub-autodetect-file",
        ]
        if sys.platform.startswith("linux"):
            args.append("--no-xlib")
        self._instance = vlc.Instance(*args)
        self._player = self._instance.media_player_new()
        self._loaded: Optional[str] = None

    # ----- embedding -----
    def attach_to_widget(self, widget) -> None:
        """Attach libvlc output to the native window handle of a Qt widget."""
        wid = int(widget.winId())
        if sys.platform.startswith("linux"):
            self._player.set_xwindow(wid)
        elif sys.platform == "win32":
            self._player.set_hwnd(wid)
        elif sys.platform == "darwin":
            self._player.set_nsobject(wid)

    # ----- transport -----
    def load(self, path: str) -> None:
        media = self._instance.media_new(path)
        self._player.set_media(media)
        self._loaded = path

    def _is_ended(self) -> bool:
        """True when the current media has reached EOF.

        Once libvlc reaches ``State.Ended`` it ignores ``play()`` and
        ``set_time()`` until a fresh ``set_media`` is installed, which
        is why naively clicking Play after EOF does nothing.
        """
        try:
            return self._player.get_state() == vlc.State.Ended
        except Exception:
            return False

    def _rewind_if_ended(self) -> None:
        """Re-arm the player so it can play again after reaching EOF."""
        if not self._is_ended() or self._loaded is None:
            return
        # Stopping first clears the Ended state; re-setting the same
        # media gives libvlc a fresh playback cursor at 0.
        self._player.stop()
        media = self._instance.media_new(self._loaded)
        self._player.set_media(media)

    def play(self) -> None:
        self._rewind_if_ended()
        self._player.play()

    def pause(self) -> None:
        # `set_pause(1)` is more reliable than `pause()` which toggles.
        self._player.set_pause(1)

    def toggle(self) -> None:
        if self.is_playing():
            self.pause()
        else:
            self.play()

    def stop(self) -> None:
        self._player.stop()

    # ----- positioning -----
    def position_ms(self) -> int:
        t = self._player.get_time()
        return int(t) if t and t > 0 else 0

    def duration_ms(self) -> int:
        m = self._player.get_media()
        if m is None:
            return 0
        # Duration may be -1 until the media is parsed.
        d = m.get_duration()
        if d <= 0:
            # Parse synchronously (fast) to get duration before playback.
            try:
                m.parse_with_options(vlc.MediaParseFlag.local, 1000)
            except Exception:
                pass
            d = m.get_duration()
        return max(0, int(d))

    def seek_ms(self, ms: int) -> None:
        # If the media ended, re-arm it first so ``set_time`` actually
        # lands somewhere instead of being silently dropped.
        self._rewind_if_ended()
        self._player.set_time(max(0, int(ms)))

    def is_playing(self) -> bool:
        return bool(self._player.is_playing())

    def set_volume(self, volume: int) -> None:
        self._player.audio_set_volume(max(0, min(100, int(volume))))

    def release(self) -> None:  # pragma: no cover
        try:
            self._player.stop()
            self._player.release()
            self._instance.release()
        except Exception:
            pass
