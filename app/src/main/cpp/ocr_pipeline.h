#pragma once
#include <memory>
#include <string>
#include <vector>

namespace paddle {
namespace lite_api { class PaddlePredictor; }
}

namespace subextract {

struct OcrLine {
    std::string text;
    float score{0.f};
};

/**
 * Three-stage Paddle Lite OCR pipeline.
 *
 *   1. Text detector  → list of quads
 *   2. Direction classifier → rotate quads to horizontal
 *   3. Recognizer → per-quad text + confidence
 *
 * The implementation in ocr_pipeline.cpp follows the upstream Paddle Lite OCR
 * demo closely; the skeleton lives here so the Kotlin side can compile and
 * load the library even when the native dependency hasn't been fetched yet.
 */
class OcrPipeline {
public:
    OcrPipeline(const std::string& det_model,
                const std::string& cls_model,
                const std::string& rec_model,
                const std::string& label_path,
                int cpu_threads,
                bool use_gpu);
    ~OcrPipeline();

    // Input is a packed ARGB_8888 buffer (as produced by Bitmap#getPixels).
    std::vector<OcrLine> Run(const int* argb, int width, int height);

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

}  // namespace subextract
