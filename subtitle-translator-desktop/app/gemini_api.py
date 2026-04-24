"""Gemini translation client.

Uses Google's Generative Language REST API directly so we don't pull the
full ``google-generativeai`` SDK (keeps the PyInstaller bundle small and
avoids the heavy ``grpcio`` transitive dependency).

The key is read from the ``GEMINI_API_KEY`` environment variable.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterable, List, Optional


GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)
DEFAULT_MODEL = "gemini-1.5-flash-latest"

SYSTEM_PROMPT = (
    "Translate naturally like a professional subtitle translator. "
    "Keep it concise, emotional, and context-aware. "
    "Preserve line breaks exactly. Do NOT add quotes, commentary, or "
    "extra prefixes — output only the translated subtitle text."
)


class GeminiError(RuntimeError):
    """Raised for any translation failure so the UI can surface it."""


def _api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise GeminiError(
            "GEMINI_API_KEY environment variable is not set. "
            "Export it before launching the app."
        )
    return key


def _post(url: str, payload: dict, timeout: int = 30) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise GeminiError(f"HTTP {e.code}: {detail[:500]}") from e
    except urllib.error.URLError as e:
        raise GeminiError(f"Network error: {e.reason}") from e
    except Exception as e:  # pragma: no cover
        raise GeminiError(str(e)) from e


def _extract_text(response: dict) -> str:
    candidates = response.get("candidates") or []
    if not candidates:
        raise GeminiError("Empty response from Gemini.")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    pieces: List[str] = []
    for p in parts:
        if "text" in p:
            pieces.append(p["text"])
    text = "".join(pieces).strip()
    if not text:
        raise GeminiError("Gemini returned no text content.")
    return text


class GeminiTranslator:
    """Simple, stateless translator. Safe to call from background threads."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        target_language: str = "English",
    ) -> None:
        self.model = model
        self.target_language = target_language

    # Allow the UI to update the target language at runtime.
    def set_target_language(self, language: str) -> None:
        self.target_language = language.strip() or "English"

    def _endpoint(self) -> str:
        key = _api_key()
        base = GEMINI_ENDPOINT.format(model=urllib.parse.quote(self.model))
        return f"{base}?key={urllib.parse.quote(key)}"

    def translate(self, text: str, context: Optional[str] = None) -> str:
        if not text.strip():
            return ""
        user_prompt = (
            f"Target language: {self.target_language}\n"
            f"Subtitle to translate:\n{text}"
        )
        if context:
            user_prompt = f"Context (do not translate):\n{context}\n\n" + user_prompt
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            "generationConfig": {
                "temperature": 0.3,
                "topP": 0.95,
                "maxOutputTokens": 512,
            },
        }
        data = _post(self._endpoint(), payload)
        return _extract_text(data)

    def translate_batch(
        self,
        texts: Iterable[str],
        progress_cb=None,
    ) -> List[str]:
        """Translate a list of subtitles one by one.

        A callable ``progress_cb(done, total, current_text)`` may be
        supplied; it is invoked from the calling thread after each item.
        """
        items = list(texts)
        out: List[str] = []
        total = len(items)
        for i, t in enumerate(items, start=1):
            out.append(self.translate(t))
            if progress_cb is not None:
                try:
                    progress_cb(i, total, out[-1])
                except Exception:
                    pass
        return out
