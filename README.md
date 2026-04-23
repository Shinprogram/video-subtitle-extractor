# VideoSubtitleExtractor

Android app that **extracts subtitles from any video** using on-device OCR,
lets you preview them in sync with playback, edit them, translate them via the
Gemini API, and export to `.srt`.

## Highlights

- 100 % Kotlin, **Jetpack Compose** + Material 3 UI, edge-to-edge, dynamic
  color, dark / light automatic.
- **Clean-ish architecture** — `domain → data → ui` with Hilt-wired repositories.
- **ExoPlayer (Media3 1.4)** for playback, with a Compose overlay that renders
  the currently-active cue.
- **Two swappable OCR engines** behind a small `OcrEngine` interface:
  - **ML Kit Text Recognition** (default — Latin + Chinese, zero-config).
  - **PaddleOCR PP-OCRv3** via Paddle Lite JNI — enabled automatically once
    `scripts/download_paddle_models.sh` has been run.
- **OCR pipeline** = frame sampling (MediaMetadataRetriever) → lower-third
  crop → OCR → denoise/clean → dedupe consecutive frames → merge runs → SRT.
- **WorkManager** foreground job for long extractions so Android doesn't kill
  it mid-way through.
- **Gemini 1.5 Flash** translation, chunked to respect the context window.
- **Snapdragon / GPU toggle** that flips the Paddle Lite backend to OpenCL
  when supported (falls back to CPU automatically).
- **SRT export** through the Storage Access Framework — works on any Android
  10+ device without storage permissions.

## Quick start

```bash
# 1. Clone and open in Android Studio Koala (2024.1) or newer.
git clone https://github.com/Shinprogram/video-subtitle-extractor.git
cd video-subtitle-extractor

# 2. (Optional but recommended) pull PaddleOCR models + Paddle Lite:
./scripts/download_paddle_models.sh

# 3. Configure your API key (optional — can also be entered in Settings):
cp local.properties.example local.properties
$EDITOR local.properties     # set GEMINI_API_KEY=…  and sdk.dir=…

# 4. Build & install a debug APK:
./gradlew :app:installDebug
```

Min SDK **24 (Android 7.0)**, target SDK **34**. Kotlin 2.0, AGP 8.5.

## Module / package layout

```
app/
├── src/main/java/com/shinprogram/subextract/
│   ├── MainActivity.kt / SubExtractApp.kt       ← entry points
│   ├── di/AppModule.kt                          ← Hilt graph
│   ├── domain/{model,repository}/               ← pure Kotlin, no Android deps
│   ├── data/{db,datastore,repository}/          ← Room + DataStore + impls
│   ├── ocr/                                     ← pipeline & engines
│   │   ├── FrameSampler.kt                      ← MediaMetadataRetriever
│   │   ├── SubtitleExtractor.kt                 ← orchestrator
│   │   ├── TextFilter.kt / SrtGenerator.kt
│   │   ├── MlKitOcrEngine.kt                    ← default engine
│   │   └── paddle/{PaddleOcrEngine.kt,PaddleOcrJni.kt}
│   ├── translate/{GeminiClient.kt, ...}         ← Retrofit + kotlinx.serialization
│   ├── player/                                  ← ExoPlayer wiring (in ui/screens/player)
│   ├── work/OcrWorker.kt                        ← foreground extraction job
│   └── ui/
│       ├── navigation/AppNavHost.kt
│       ├── theme/                               ← Material 3 colours / typography
│       ├── common/ActiveTrackHolder.kt          ← shared Player ↔ Editor state
│       └── screens/{home,player,editor,settings}/
└── src/main/cpp/                                ← Paddle Lite JNI glue
    ├── CMakeLists.txt
    ├── paddle_native.cpp
    └── ocr_pipeline.{h,cpp}
```

Tests live in `app/src/test` (unit) and `app/src/androidTest` (instrumented).

## Extraction pipeline

```
┌───────────┐   ┌───────────────┐   ┌──────────────┐
│  video    │──▶│ FrameSampler  │──▶│ crop lower ⅓ │──▶ OcrEngine
└───────────┘   │  (MMR, 2 fps) │   └──────────────┘        │
                └───────────────┘                           ▼
                                                    ┌────────────┐
                                                    │ TextFilter │
                                                    │  clean +   │
                                                    │  dedupe    │
                                                    └────────────┘
                                                          │
                                                          ▼
                                                  List<Subtitle>
                                                          │
                                                          ▼
                                                    SrtGenerator
```

The sampler uses `MediaMetadataRetriever.getScaledFrameAtTime` so we never
allocate a full-resolution bitmap. Defaults are tuned for readable burned-in
subtitles (2 fps, 33 % bottom crop, 80 % Levenshtein-similarity dedupe).

## Translation

`TranslationRepositoryImpl` talks to
`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent`.
Cues are chunked (40 at a time) so one failure doesn't discard the whole file,
and the prompt asks Gemini to return a numbered list to keep ordering robust.

At runtime the API key comes from, in order:
1. A value pasted into **Settings → Gemini API key** (DataStore-backed).
2. `GEMINI_API_KEY` in `local.properties` (compiled into `BuildConfig`).

## GPU / Snapdragon optimisation

The **Settings → Prefer GPU / NNAPI** switch is persisted and passed through
to `PaddleOcrJni.init(…, useGpu = …)`, which, when the Paddle Lite library is
present, configures the predictor with the OpenCL backend (available on
Adreno GPUs). The ML Kit engine delegates accelerator selection to Google Play
Services.

## Export

Subtitle export is routed through `ActivityResultContracts.CreateDocument`.
The resulting SRT file is written straight to the user-chosen SAF location —
no `WRITE_EXTERNAL_STORAGE` permission is requested.

## Running tests / lint

```bash
./gradlew :app:testDebugUnitTest
./gradlew :app:lintDebug
./gradlew :app:assembleDebug
```

CI (`.github/workflows/ci.yml`) runs the same three tasks on every PR and
uploads the debug APK as a build artefact.

## License

MIT. See [LICENSE](LICENSE).
