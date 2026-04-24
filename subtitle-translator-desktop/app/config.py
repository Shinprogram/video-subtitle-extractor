"""Persistent user config (API key, prompt, font, batch/delay tuning).

Stored as JSON under the platform's standard user-config location:

* Linux  : ``~/.config/subtitle-translator/config.json``
* macOS  : ``~/Library/Application Support/subtitle-translator/config.json``
* Windows: ``%APPDATA%\\subtitle-translator\\config.json``

We deliberately do **not** use :mod:`QSettings` so this module is
importable (and unit-testable) without Qt.

Secrets are kept in this file on the user's machine. The file is
created with ``chmod 600`` on POSIX to keep the API key off-limits to
other users on multi-user systems.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict


DEFAULT_PROMPT = (
    "Translate subtitles into natural Vietnamese. "
    "Keep emotional tone, context, and concise subtitle style. "
    "Do not merge lines. Keep numbering."
)

DEFAULT_FONT_FAMILY = "Sans Serif"
DEFAULT_FONT_SIZE_PX = 20
DEFAULT_BATCH_SIZE = 40
DEFAULT_REQUEST_DELAY_MS = 1500
DEFAULT_MODEL = "gemini-1.5-flash-latest"


def _user_config_dir() -> Path:
    """Return the platform's per-user config directory for the app."""
    if sys.platform == "win32":
        root = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(root) / "subtitle-translator"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "subtitle-translator"
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(xdg) / "subtitle-translator"


def default_config_path() -> Path:
    return _user_config_dir() / "config.json"


@dataclass
class AppConfig:
    """All user-tunable settings.

    ``api_key`` is stored here rather than pulled from an environment
    variable so users can configure it from the Settings dialog without
    needing a shell. Env var ``GEMINI_API_KEY`` is still accepted at
    runtime as a fallback when this field is empty.
    """

    api_key: str = ""
    prompt: str = DEFAULT_PROMPT
    font_family: str = DEFAULT_FONT_FAMILY
    font_size_px: int = DEFAULT_FONT_SIZE_PX
    batch_size: int = DEFAULT_BATCH_SIZE
    request_delay_ms: int = DEFAULT_REQUEST_DELAY_MS
    target_language: str = "Vietnamese"
    model: str = DEFAULT_MODEL
    # Fields we want to preserve across loads even if we didn't
    # explicitly declare them above. The ``load`` path merges unknown
    # keys into this dict so newer installs don't clobber them.
    extras: Dict[str, Any] = field(default_factory=dict)

    # -- IO --------------------------------------------------------
    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        p = Path(path) if path is not None else default_config_path()
        if not p.exists():
            return cls()
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Corrupted config — fall back to defaults rather than crash.
            return cls()
        if not isinstance(raw, dict):
            return cls()
        known: Dict[str, Any] = {}
        extras: Dict[str, Any] = {}
        declared = {f for f in cls.__dataclass_fields__ if f != "extras"}
        for k, v in raw.items():
            if k in declared:
                known[k] = v
            else:
                extras[k] = v
        cfg = cls(**known)
        cfg.extras = extras
        cfg._clamp()
        return cfg

    def save(self, path: Path | None = None) -> Path:
        p = Path(path) if path is not None else default_config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        # Merge extras back so they round-trip unmodified.
        extras = data.pop("extras", {}) or {}
        data.update(extras)
        text = json.dumps(data, indent=2, ensure_ascii=False)
        p.write_text(text, encoding="utf-8")
        # Tighten permissions on POSIX (the file may contain an API key).
        if sys.platform != "win32":
            try:
                os.chmod(p, 0o600)
            except OSError:
                pass
        return p

    # -- helpers ---------------------------------------------------
    def resolved_api_key(self) -> str:
        """Return the effective key: config value, or env fallback."""
        if self.api_key.strip():
            return self.api_key.strip()
        return os.environ.get("GEMINI_API_KEY", "").strip()

    def _clamp(self) -> None:
        # Defensive clamping — a hand-edited config should not break the app.
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            self.prompt = DEFAULT_PROMPT
        if not isinstance(self.font_family, str) or not self.font_family.strip():
            self.font_family = DEFAULT_FONT_FAMILY
        try:
            self.font_size_px = max(8, min(72, int(self.font_size_px)))
        except (TypeError, ValueError):
            self.font_size_px = DEFAULT_FONT_SIZE_PX
        try:
            self.batch_size = max(1, min(200, int(self.batch_size)))
        except (TypeError, ValueError):
            self.batch_size = DEFAULT_BATCH_SIZE
        try:
            self.request_delay_ms = max(0, min(60000, int(self.request_delay_ms)))
        except (TypeError, ValueError):
            self.request_delay_ms = DEFAULT_REQUEST_DELAY_MS
