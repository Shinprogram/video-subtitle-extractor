#!/usr/bin/env bash
# Fetches the PP-OCRv3 mobile models and the Paddle Lite Android prebuilt
# library. Run once after cloning — the resulting files are intentionally
# ignored by git.
#
# After this script completes successfully:
#   * ./app/src/main/assets/ocr/paddle/*.nb    — model weights
#   * ./app/libs/paddle_lite/<abi>/...          — prebuilt Paddle Lite runtime
# and subsequent Gradle builds will include the native C++ code automatically.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ASSETS="$ROOT/app/src/main/assets/ocr/paddle"
LIBS="$ROOT/app/libs/paddle_lite"
mkdir -p "$ASSETS" "$LIBS"

echo "→ Downloading PP-OCRv3 detection / classification / recognition weights"
BASE="https://paddleocr.bj.bcebos.com"
curl -fsSL -o "$ASSETS/ch_PP-OCRv3_det_slim_opt.nb" \
    "$BASE/PP-OCRv3/lite/ch_PP-OCRv3_det_slim_opt.nb"
curl -fsSL -o "$ASSETS/ch_PP-OCRv3_rec_slim_opt.nb" \
    "$BASE/PP-OCRv3/lite/ch_PP-OCRv3_rec_slim_opt.nb"
curl -fsSL -o "$ASSETS/ch_ppocr_mobile_v2.0_cls_slim_opt.nb" \
    "$BASE/dygraph_v2.0/lite/ch_ppocr_mobile_v2.0_cls_slim_opt.nb"
curl -fsSL -o "$ASSETS/ppocr_keys_v1.txt" \
    "https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/release/2.7/ppocr/utils/ppocr_keys_v1.txt"

echo "→ Downloading Paddle Lite Android v2.10 (arm64-v8a / armeabi-v7a)"
TMP=$(mktemp -d)
curl -fsSL -o "$TMP/paddle_lite.tar.gz" \
    "https://github.com/PaddlePaddle/Paddle-Lite/releases/download/v2.10/inference_lite_lib.android.armv8.armv7.clang.with_extra.tar.gz"
tar -xzf "$TMP/paddle_lite.tar.gz" -C "$TMP"

mkdir -p "$LIBS/arm64-v8a" "$LIBS/armeabi-v7a"
cp -r "$TMP/inference_lite_lib.android.armv8"/cxx/lib/libpaddle_api_shared.so   "$LIBS/arm64-v8a/"   || true
cp -r "$TMP/inference_lite_lib.android.armv8"/cxx/include                       "$LIBS/arm64-v8a/"   || true
cp -r "$TMP/inference_lite_lib.android.armv7"/cxx/lib/libpaddle_api_shared.so   "$LIBS/armeabi-v7a/" || true
cp -r "$TMP/inference_lite_lib.android.armv7"/cxx/include                       "$LIBS/armeabi-v7a/" || true

echo "✓ Done. Rebuild the app:   ./gradlew :app:assembleDebug"
