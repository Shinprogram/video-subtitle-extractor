// JNI entry points for Paddle Lite-based OCR. Kept thin — the actual pipeline
// (detector → classifier → recognizer) lives in ocr_pipeline.cpp.
//
// This file is only compiled when the Paddle Lite prebuilt library is present
// under app/libs/paddle_lite/. See scripts/download_paddle_models.sh.

#include <android/log.h>
#include <jni.h>
#include <string>
#include <vector>

#include "ocr_pipeline.h"

#define LOG_TAG "PaddleOcrJni"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

extern "C" {

JNIEXPORT jlong JNICALL
Java_com_shinprogram_subextract_ocr_paddle_PaddleOcrJni_init(
    JNIEnv* env, jclass, jstring detPath, jstring clsPath, jstring recPath,
    jstring labelPath, jint threads, jboolean useGpu) {

    auto toStr = [&](jstring s) {
        const char* c = env->GetStringUTFChars(s, nullptr);
        std::string out(c);
        env->ReleaseStringUTFChars(s, c);
        return out;
    };

    try {
        auto* pipe = new subextract::OcrPipeline(
            toStr(detPath), toStr(clsPath), toStr(recPath), toStr(labelPath),
            threads, useGpu == JNI_TRUE);
        return reinterpret_cast<jlong>(pipe);
    } catch (const std::exception& e) {
        LOGE("init failed: %s", e.what());
        return 0;
    }
}

JNIEXPORT jobjectArray JNICALL
Java_com_shinprogram_subextract_ocr_paddle_PaddleOcrJni_runOcr(
    JNIEnv* env, jclass, jlong handle, jintArray argb, jint width, jint height) {

    auto* pipe = reinterpret_cast<subextract::OcrPipeline*>(handle);
    if (pipe == nullptr) return nullptr;

    jint* pixels = env->GetIntArrayElements(argb, nullptr);
    if (pixels == nullptr) return nullptr;

    std::vector<subextract::OcrLine> lines;
    try {
        lines = pipe->Run(pixels, width, height);
    } catch (const std::exception& e) {
        LOGE("runOcr failed: %s", e.what());
    }
    env->ReleaseIntArrayElements(argb, pixels, JNI_ABORT);

    jclass lineClass = env->FindClass(
        "com/shinprogram/subextract/ocr/paddle/PaddleOcrJni$Line");
    if (lineClass == nullptr) return nullptr;
    jmethodID ctor = env->GetMethodID(lineClass, "<init>", "(Ljava/lang/String;F)V");

    jobjectArray out = env->NewObjectArray((jsize) lines.size(), lineClass, nullptr);
    for (size_t i = 0; i < lines.size(); ++i) {
        jstring text = env->NewStringUTF(lines[i].text.c_str());
        jobject obj = env->NewObject(lineClass, ctor, text, lines[i].score);
        env->SetObjectArrayElement(out, (jsize) i, obj);
        env->DeleteLocalRef(text);
        env->DeleteLocalRef(obj);
    }
    return out;
}

JNIEXPORT void JNICALL
Java_com_shinprogram_subextract_ocr_paddle_PaddleOcrJni_destroy(
    JNIEnv*, jclass, jlong handle) {
    delete reinterpret_cast<subextract::OcrPipeline*>(handle);
}

}  // extern "C"
