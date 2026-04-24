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
│   ├── subtitle_parser.py   # SRT parsing / serialization
│   ├── video_player.py      # Thin python-vlc wrapper
│   ├── gemini_api.py        # Gemini REST client
│   └── ui/
│       ├── main_window.py   # Main Qt window + layout
│       ├── workers.py       # QThread workers for translation
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

Create a key at <https://aistudio.google.com/app/apikey>, then:

```bash
# macOS / Linux
export GEMINI_API_KEY="your-key-here"

# Windows (PowerShell)
$Env:GEMINI_API_KEY = "your-key-here"
```

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

Launch the packaged app the same way as the source version — with
`GEMINI_API_KEY` set in the environment.

## Notes on architecture

- **Subtitle sync** is driven by a 100 ms `QTimer` that polls the VLC clock
  and uses a binary search (`SubtitleDocument.entry_at`) to find the active
  cue — O(log n) per tick even for huge SRTs.
- **Translation calls** run in `QThread` workers (see `app/ui/workers.py`) so
  the UI thread never blocks. Individual translations and full-batch
  translations both report progress via Qt signals.
- **Overlay rendering** is a plain `QLabel` child of the video frame,
  repositioned on every resize. This works cross-platform without having to
  poke at libvlc's native subtitle track.
- **Gemini client** talks directly to the REST API using `urllib` — no extra
  SDK needed, which keeps the PyInstaller bundle slim.
