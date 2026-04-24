"""Gemini translation client.

Uses Google's Generative Language REST API directly so we don't pull
the full ``google-generativeai`` SDK (keeps the PyInstaller bundle
small and avoids ``grpcio``).

Two entry points:

* :meth:`GeminiTranslator.translate` — single-cue translation used by
  the inline "Translate" button.
* :meth:`GeminiTranslator.translate_batch_numbered` — numbered-batch
  translation used by the ``Translate All`` worker. The prompt asks
  for ``N`` numbered lines back so the caller can strictly map output
  back to input by position.

The client does **not** loop or rate-limit itself; the caller (the
:class:`BatchTranslateWorker`) owns the retry policy and inter-batch
delay so the UI stays responsive and cancellable.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import List, Optional

from .config import AppConfig, DEFAULT_MODEL


GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)


SYSTEM_PROMPT_SINGLE = (
    "Translate naturally like a professional subtitle translator. "
    "Keep it concise, emotional, and context-aware. "
    "Preserve line breaks exactly. Do NOT add quotes, commentary, or "
    "extra prefixes — output only the translated subtitle text."
)

# Numbered-batch system prompt. The user prompt appends the per-batch
# payload. We instruct the model strictly so the response parser can
# reliably recover each numbered line.
BATCH_SYSTEM_PROMPT = (
    "You are translating subtitle lines for a video.\n"
    "You will receive a numbered list of subtitle lines and must return "
    "the SAME number of lines, in the SAME order, each prefixed with "
    "its number and a period (e.g. '1. ...', '2. ...').\n"
    "Rules:\n"
    "- Preserve the numbering exactly; never merge, split, reorder, or drop lines.\n"
    "- If a line is blank, return an empty translation but keep its number.\n"
    "- Do NOT add commentary, headings, or quotes around the translations.\n"
    "- Preserve newlines *inside* a subtitle by using the literal two-"
    "character sequence '\\n' (backslash + n) within that numbered line."
)


# Match "<number>. <rest>" at the start of a line. Tolerant of leading
# whitespace, Windows newlines, and optional trailing/leading quotes
# or bullet glyphs the model sometimes adds.
_NUMBERED_LINE_RE = re.compile(
    r"^\s*[\-\*\u2022]?\s*(\d+)\s*[\.\)\:\-]\s*(.*)$"
)


class GeminiError(RuntimeError):
    """Raised for any translation failure so the UI can surface it."""


class GeminiTransientError(GeminiError):
    """Transient failure (rate-limit / 5xx / network) — caller may retry."""


def _post(url: str, payload: dict, timeout: int = 60) -> dict:
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
        # 429 (rate limited) and 5xx responses are retryable; 4xx other
        # than 429 (bad key, bad request) are not.
        if e.code == 429 or 500 <= e.code < 600:
            raise GeminiTransientError(
                f"HTTP {e.code}: {detail[:500]}"
            ) from e
        raise GeminiError(f"HTTP {e.code}: {detail[:500]}") from e
    except urllib.error.URLError as e:
        raise GeminiTransientError(f"Network error: {e.reason}") from e
    except TimeoutError as e:
        raise GeminiTransientError(f"Timeout: {e}") from e
    except Exception as e:  # pragma: no cover - defensive
        raise GeminiError(str(e)) from e


def _extract_text(response: dict) -> str:
    candidates = response.get("candidates") or []
    if not candidates:
        # promptFeedback often explains *why* there were no candidates
        # (e.g. blocked by safety). Surface that for easier debugging.
        pf = response.get("promptFeedback") or {}
        reason = pf.get("blockReason") or "no candidates"
        raise GeminiError(f"Empty response from Gemini ({reason}).")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    pieces: List[str] = []
    for p in parts:
        if "text" in p:
            pieces.append(p["text"])
    text = "".join(pieces).strip()
    if not text:
        raise GeminiError("Gemini returned no text content.")
    return text


def parse_numbered_response(text: str, expected_count: int) -> List[str]:
    """Recover ``expected_count`` translations from a numbered batch response.

    Rules:

    * Ignore any non-numbered chrome the model adds (greetings, "Sure!",
      markdown headings, code fences) — we only look at lines that
      begin with ``<n>.``.
    * Allow continuation lines: a line that does NOT match the numbered
      prefix is appended (joined with ``\\n``) to the last seen index.
    * If some indices are missing, they come back as empty strings.

    Raises :class:`GeminiError` if **zero** numbered lines were found —
    that's almost always a broken response worth reporting.
    """
    if expected_count <= 0:
        return []
    out = [""] * expected_count
    seen_any = False
    current_idx: Optional[int] = None

    # Normalise CRLF and strip markdown code fences that Gemini
    # occasionally wraps the whole payload in.
    normalised = text.replace("\r\n", "\n").strip()
    if normalised.startswith("```"):
        # Drop the opening fence (possibly with a language tag) and any
        # closing fence at the very end.
        normalised = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", normalised)
        if normalised.endswith("```"):
            normalised = normalised[: -3].rstrip()

    for raw in normalised.split("\n"):
        m = _NUMBERED_LINE_RE.match(raw)
        if m:
            try:
                n = int(m.group(1))
            except ValueError:
                continue
            body = m.group(2).rstrip()
            if 1 <= n <= expected_count:
                out[n - 1] = body
                current_idx = n - 1
                seen_any = True
            else:
                # Out-of-range index: treat as a stray line. Append to
                # the most recent numbered line if any, otherwise drop.
                if current_idx is not None:
                    out[current_idx] = (out[current_idx] + "\n" + raw).strip()
        else:
            stripped = raw.strip()
            if not stripped:
                continue
            # Continuation of the previous numbered line, or unrelated
            # chrome if we haven't hit a numbered line yet.
            if current_idx is not None:
                out[current_idx] = (out[current_idx] + "\n" + stripped).strip()

    if not seen_any:
        raise GeminiError(
            "Batch response contained no numbered lines. "
            f"Got: {normalised[:200]!r}"
        )

    # Convert the literal '\n' escape we asked the model to use back
    # into a real newline so the UI renders multi-line cues correctly.
    out = [piece.replace("\\n", "\n") for piece in out]
    return out


class GeminiTranslator:
    """Stateless-ish translator. Safe to call from background threads.

    Holds a reference to :class:`AppConfig` so UI-level changes to the
    API key / prompt / target language propagate immediately without
    having to recreate the worker.
    """

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self.config = config or AppConfig()

    def _endpoint(self) -> str:
        key = self.config.resolved_api_key()
        if not key:
            raise GeminiError(
                "Gemini API key is not configured. "
                "Open Settings and paste your key, or set the "
                "GEMINI_API_KEY environment variable."
            )
        model = self.config.model or DEFAULT_MODEL
        base = GEMINI_ENDPOINT.format(model=urllib.parse.quote(model))
        return f"{base}?key={urllib.parse.quote(key)}"

    # ----- single-cue ---------------------------------------------
    def translate(self, text: str, context: Optional[str] = None) -> str:
        if not text.strip():
            return ""
        user_prompt = (
            f"Target language: {self.config.target_language}\n"
            f"Subtitle to translate:\n{text}"
        )
        if context:
            user_prompt = f"Context (do not translate):\n{context}\n\n" + user_prompt
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT_SINGLE}]},
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

    # ----- numbered batch -----------------------------------------
    def translate_batch_numbered(self, texts: List[str]) -> List[str]:
        """Send ONE request per batch. Expects N numbered lines back.

        The returned list has exactly ``len(texts)`` items; any line
        the model failed to return is filled with an empty string and
        the caller is responsible for flagging the mismatch.
        """
        if not texts:
            return []
        # Encode newlines *inside* a cue as the literal two-character
        # escape "\n" so the per-line numbering is unambiguous.
        numbered_lines = []
        for i, t in enumerate(texts, start=1):
            safe = t.replace("\n", "\\n") if t else ""
            numbered_lines.append(f"{i}. {safe}")
        payload_text = "\n".join(numbered_lines)

        user_prompt = (
            f"Target language: {self.config.target_language}\n"
            f"User translation style preferences:\n{self.config.prompt}\n\n"
            f"Subtitle lines to translate (return EXACTLY {len(texts)} "
            "numbered lines in the same order):\n"
            f"{payload_text}"
        )
        payload = {
            "system_instruction": {"parts": [{"text": BATCH_SYSTEM_PROMPT}]},
            "contents": [
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            "generationConfig": {
                "temperature": 0.3,
                "topP": 0.95,
                # Budget ~256 tokens per line, capped.
                "maxOutputTokens": min(8192, 256 * max(1, len(texts))),
            },
        }
        data = _post(self._endpoint(), payload)
        raw = _extract_text(data)
        return parse_numbered_response(raw, len(texts))
