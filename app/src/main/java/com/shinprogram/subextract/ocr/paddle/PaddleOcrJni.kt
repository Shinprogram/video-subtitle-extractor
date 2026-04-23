package com.shinprogram.subextract.ocr.paddle

/**
 * Thin JNI bridge to the Paddle Lite runtime. See
 * `app/src/main/cpp/paddle_native.cpp` for the C++ side.
 *
 * All methods may block on native I/O — callers must invoke them from a
 * background dispatcher.
 */
internal object PaddleOcrJni {

    data class Line(val text: String, val score: Float)

    @JvmStatic external fun init(
        detModelPath: String,
        clsModelPath: String,
        recModelPath: String,
        labelPath: String,
        cpuThreadNum: Int,
        useGpu: Boolean,
    ): Long

    @JvmStatic external fun runOcr(
        handle: Long,
        argb: IntArray,
        width: Int,
        height: Int,
    ): Array<Line>?

    @JvmStatic external fun destroy(handle: Long)
}
