package com.shinprogram.subextract.ocr.paddle

import android.content.Context
import android.graphics.Bitmap
import android.util.Log
import com.shinprogram.subextract.ocr.OcrEngine
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Wrapper around the Paddle Lite PP-OCRv3 pipeline (detection + classification
 * + recognition). The native library and the three `.nb` model files must be
 * present on disk at first use; see `scripts/download_paddle_models.sh` and the
 * project README for how to fetch them.
 *
 * When the native library is missing the engine marks itself as unavailable,
 * letting callers transparently fall back to [com.shinprogram.subextract.ocr.MlKitOcrEngine].
 */
@Singleton
class PaddleOcrEngine @Inject constructor(
    @ApplicationContext private val context: Context,
) : OcrEngine {

    override val id: String = "paddle"

    private val lock = Mutex()

    @Volatile private var nativeHandle: Long = 0L
    @Volatile private var loadFailed: Boolean = false

    init {
        try {
            System.loadLibrary(NATIVE_LIB)
        } catch (t: Throwable) {
            Log.w(TAG, "Native Paddle Lite library not bundled; engine disabled.", t)
            loadFailed = true
        }
    }

    override suspend fun isAvailable(): Boolean {
        if (loadFailed) return false
        return lock.withLock { ensureInitialized() } != 0L
    }

    override suspend fun recognize(bitmap: Bitmap): String = withContext(Dispatchers.Default) {
        val handle = lock.withLock { ensureInitialized() }
        if (handle == 0L) return@withContext ""
        val argb = IntArray(bitmap.width * bitmap.height)
        bitmap.getPixels(argb, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height)
        PaddleOcrJni.runOcr(handle, argb, bitmap.width, bitmap.height)
            ?.joinToString(separator = "\n") { it.text.trim() }
            ?.trim()
            .orEmpty()
    }

    override fun close() {
        if (nativeHandle != 0L) {
            PaddleOcrJni.destroy(nativeHandle)
            nativeHandle = 0L
        }
    }

    private fun ensureInitialized(): Long {
        if (loadFailed) return 0L
        if (nativeHandle != 0L) return nativeHandle
        val modelDir = stageAssetsIfNeeded()
        if (!modelDir.exists()) {
            loadFailed = true
            return 0L
        }
        nativeHandle = try {
            PaddleOcrJni.init(
                detModelPath = File(modelDir, "ch_PP-OCRv3_det_slim_opt.nb").absolutePath,
                clsModelPath = File(modelDir, "ch_ppocr_mobile_v2.0_cls_slim_opt.nb").absolutePath,
                recModelPath = File(modelDir, "ch_PP-OCRv3_rec_slim_opt.nb").absolutePath,
                labelPath = File(modelDir, "ppocr_keys_v1.txt").absolutePath,
                cpuThreadNum = 4,
                useGpu = false,
            )
        } catch (t: Throwable) {
            Log.w(TAG, "PaddleOcrJni.init failed", t)
            loadFailed = true
            0L
        }
        return nativeHandle
    }

    /**
     * Copies `.nb` model assets (if present in `assets/ocr/paddle/`) to the app
     * cache so native code can `mmap` them. Returns the destination directory
     * regardless of whether files were actually present.
     */
    private fun stageAssetsIfNeeded(): File {
        val dest = File(context.filesDir, "paddle_models")
        if (dest.exists() && (dest.listFiles()?.isNotEmpty() == true)) return dest
        dest.mkdirs()
        val mgr = context.assets
        val names = try { mgr.list(ASSET_DIR)?.toList().orEmpty() } catch (_: Throwable) { emptyList() }
        for (name in names) {
            val out = File(dest, name)
            if (out.exists()) continue
            runCatching {
                mgr.open("$ASSET_DIR/$name").use { input ->
                    FileOutputStream(out).use { output -> input.copyTo(output) }
                }
            }.onFailure { Log.w(TAG, "Could not stage asset $name", it) }
        }
        return dest
    }

    private companion object {
        const val TAG = "PaddleOcrEngine"
        const val NATIVE_LIB = "subextract_paddle"
        const val ASSET_DIR = "ocr/paddle"
    }
}
