package com.shinprogram.subextract.ocr

import android.graphics.Bitmap

/**
 * Contract satisfied by both the default ML Kit engine and the optional
 * PaddleOCR engine. Keeping the interface narrow lets the pipeline swap
 * engines without changing the rest of the code.
 */
interface OcrEngine {
    /** Human-readable identifier, useful for logs and analytics. */
    val id: String

    /** Whether the engine is currently usable (models loaded, libs present, …). */
    suspend fun isAvailable(): Boolean

    /**
     * Runs OCR on [bitmap] and returns the recognised text, concatenated with
     * newlines when multiple lines are present. Returns an empty string when no
     * text was confidently detected.
     */
    suspend fun recognize(bitmap: Bitmap): String

    /** Frees any native resources. Safe to call more than once. */
    fun close() {}
}
