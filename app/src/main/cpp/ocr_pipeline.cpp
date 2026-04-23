// Minimal Paddle Lite OCR pipeline driver.
//
// Upstream reference: https://github.com/PaddlePaddle/Paddle-Lite-Demo/tree/master/ocr
// The detector/classifier/recognizer handles are created eagerly; inference is
// driven per-frame by `Run`. The full post-processing (DB non-max suppression,
// CTC decoding) is deliberately left out of this repo — only compiled when the
// Paddle Lite prebuilt library has been fetched via `scripts/download_paddle_models.sh`.

#include "ocr_pipeline.h"

#include <android/log.h>
#include <fstream>
#include <stdexcept>

#define LOG_TAG "OcrPipeline"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

namespace subextract {

class OcrPipeline::Impl {
public:
    Impl(const std::string& det_model,
         const std::string& cls_model,
         const std::string& rec_model,
         const std::string& label_path,
         int cpu_threads,
         bool use_gpu)
        : det_(det_model), cls_(cls_model), rec_(rec_model),
          threads_(cpu_threads), use_gpu_(use_gpu) {
        LoadLabels(label_path);
        // Real predictor construction (MobileConfig, CreatePaddlePredictor<>()) lives
        // in the Paddle Lite demo and is wired in once libpaddle_api_shared.so is
        // copied into app/libs/paddle_lite/.
    }

    std::vector<OcrLine> Run(const int* /*argb*/, int /*w*/, int /*h*/) {
        // Placeholder: returns no lines until the full pipeline is wired in.
        // Ship the kotlin MlKit engine as the default runtime; Paddle becomes
        // the preferred engine once the prebuilt library exists on disk.
        return {};
    }

private:
    void LoadLabels(const std::string& path) {
        std::ifstream in(path);
        if (!in) { LOGE("cannot open label file %s", path.c_str()); return; }
        std::string line;
        while (std::getline(in, line)) labels_.emplace_back(std::move(line));
    }

    std::string det_, cls_, rec_;
    int threads_;
    bool use_gpu_;
    std::vector<std::string> labels_;
};

OcrPipeline::OcrPipeline(const std::string& det_model,
                         const std::string& cls_model,
                         const std::string& rec_model,
                         const std::string& label_path,
                         int cpu_threads, bool use_gpu)
    : impl_(new Impl(det_model, cls_model, rec_model, label_path, cpu_threads, use_gpu)) {}

OcrPipeline::~OcrPipeline() = default;

std::vector<OcrLine> OcrPipeline::Run(const int* argb, int w, int h) {
    return impl_->Run(argb, w, h);
}

}  // namespace subextract
