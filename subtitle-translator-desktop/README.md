# Subtitle Translator — AI-Powered Desktop App

A modern, dark-themed desktop app for translating and editing SRT subtitles in
real-time alongside video playback. Built with **PyQt5** + **python-vlc** and
the **Gemini API**, and packaged as a Windows `.exe` via PyInstaller.

![app preview](docs/screenshot.png)

## Features

- Load a video and `.srt` file side by side.
- Smooth VLC-powered video playback with seek bar, play/pause, and live
  timestamp readout.
- Subtitle overlay rendered on top of the video (white text on a
  semi-transparent black background, max 2 lines, auto centered).
- Scrollable subtitle list — double-click any row to jump to it.
- Inline editor with **Apply Changes** that updates the overlay instantly.
- **Translate** a single cue or **Translate All** via Gemini (runs in a
  background thread so the UI stays snappy).
- Numbered **batch translation** — groups cues into batches of 40 lines
  (configurable) and sends one API request per batch, preserving strict
  order.
- Rate-limit protection: configurable delay between batches (default
  1.5 s) and automatic retry up to 3 times with exponential backoff
  (1 s → 2 s → 4 s) on HTTP 429 / 5xx / network errors.
- **Settings dialog** (toolbar → Settings…) persists per-user to
  `config.json`:
  - Gemini API key (no need to export an env var)
  - Custom translation prompt
  - Target language
  - Overlay font family + size
  - Batch size and inter-batch delay
- Subtitle overlay pauses and hides automatically when the window is
  minimised — no ghost subtitles on top of other apps.
- Subtitle delay adjustment (+/- seconds) to fix mis-synced subtitles.
- Export edited / translated subtitles back to `.srt`.
- Keyboard shortcuts:
  - `Space` — Play / Pause
  - `Ctrl+Enter` — Apply subtitle edit
  - `Ctrl+S` — Export SRT

## Project layout

```
subtitle-translator-desktop/
├── main.py                  # App entrypoint
├── app/
│   ├── config.py            # User config (JSON) — API key, prompt, font, rate limits
│   ├── subtitle_parser.py   # SRT parsing / serialization
│   ├── video_player.py      # Thin python-vlc wrapper
│   ├── gemini_api.py        # Gemini REST client (single + numbered-batch)
│   └── ui/
│       ├── main_window.py   # Main Qt window + layout
│       ├── settings_dialog.py  # Settings editor
│       ├── workers.py       # QThread workers (batched + rate-limited)
│       └── styles.py        # Dark-theme QSS stylesheet
├── requirements.txt
├── requirements-dev.txt
└── subtitle_translator.spec # PyInstaller build spec
```

## Setup

### 1. Install VLC (system-level)

`python-vlc` is a binding and needs the actual VLC runtime installed.

- **Windows**: download the installer from <https://www.videolan.org/vlc/> and
  install. Match the bitness of your Python install (64-bit Python → 64-bit
  VLC).
- **macOS**: `brew install --cask vlc`.
- **Linux**: `sudo apt install vlc` (or your distro's equivalent).

### 2. Install Python dependencies

```bash
cd subtitle-translator-desktop
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set your Gemini API key

Create a key at <https://aistudio.google.com/app/apikey>. You have two
options:

1. **Recommended** — launch the app, open **Settings…** from the
   toolbar, paste the key into the *Gemini API key* field, and click
   OK. The key is persisted to `config.json` under your user config
   directory:
   - Linux: `~/.config/subtitle-translator/config.json`
   - macOS: `~/Library/Application Support/subtitle-translator/config.json`
   - Windows: `%APPDATA%\subtitle-translator\config.json`
2. **Fallback** — export `GEMINI_API_KEY` in your shell before launching:

   ```bash
   # macOS / Linux
   export GEMINI_API_KEY="your-key-here"

   # Windows (PowerShell)
   $Env:GEMINI_API_KEY = "your-key-here"
   ```

The Settings dialog value wins when both are set.

### 4. Run

```bash
python main.py
```

## Building a Windows `.exe`

```bash
pip install -r requirements-dev.txt
pyinstaller subtitle_translator.spec
```

The bundled app will be written to `dist/SubtitleTranslator/`. End users
still need the **VLC runtime** installed; this keeps the bundle small and
avoids redistributing VLC binaries.

Launch the packaged app the same way as the source version. You can
paste the Gemini API key via **Settings…** once, and it will persist
across launches.

## Notes on architecture

- **Subtitle sync** is driven by a 100 ms `QTimer` that polls the VLC clock
  and uses a binary search (`SubtitleDocument.entry_at`) to find the active
  cue — O(log n) per tick even for huge SRTs.
- **Translation calls** run in `QThread` workers (see `app/ui/workers.py`) so
  the UI thread never blocks. Individual translations and full-batch
  translations both report progress via Qt signals.
- **Batch translation** uses a numbered-line prompt: the model receives
  `1. foo\n2. bar\n…` and must return the same count in the same order.
  The parser in `gemini_api.parse_numbered_response` tolerates stray
  model chrome (markdown fences, greetings) and guarantees a result
  list of exactly `len(inputs)` — missing lines come back as empty
  strings and are surfaced to the UI as per-cue failures so the user
  can retry them individually.
- **Rate limiting** is owned by the worker, not the API client, so the
  sleep between batches is interruptible and cancellation is
  responsive. The worker retries transient errors (HTTP 429 / 5xx /
  network) up to 3 times with exponential backoff, but does NOT retry
  permanent errors (bad API key, malformed response, safety block).
- **Minimise handling** is symmetrical: on `WindowMinimized` the sync
  timer stops, the top-level overlay hides, and playback pauses;
  restoring reverses all three.
- **Overlay rendering** is a frameless top-level `QLabel` anchored in
  global screen coordinates over the video frame — this is required on
  Linux/X11 because libvlc's video output repaints over any native
  child widgets. The overlay is hidden while the window is minimised
  so it can't float over other apps.
- **Gemini client** talks directly to the REST API using `urllib` — no extra
  SDK needed, which keeps the PyInstaller bundle slim.
