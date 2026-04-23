package com.shinprogram.subextract.ocr

import android.graphics.Bitmap
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.TextRecognizer
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import kotlinx.coroutines.suspendCancellableCoroutine
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Default OCR engine. Ships with the app and needs no external models.
 *
 * Runs a Latin and a Chinese recognizer in sequence and keeps whichever returns
 * more characters — a cheap heuristic that covers the common CJK / Latin split
 * without the cost of building a full language detector.
 */
@Singleton
class MlKitOcrEngine @Inject constructor() : OcrEngine {

    override val id: String = "mlkit"

    private val latin: TextRecognizer by lazy {
        TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
    }
    private val chinese: TextRecognizer by lazy {
        TextRecognition.getClient(ChineseTextRecognizerOptions.Builder().build())
    }

    override suspend fun isAvailable(): Boolean = true

    override suspend fun recognize(bitmap: Bitmap): String {
        val input = InputImage.fromBitmap(bitmap, 0)
        val latinText = runRecognizer(latin, input)
        val chineseText = runRecognizer(chinese, input)
        return if (chineseText.length > latinText.length) chineseText else latinText
    }

    private suspend fun runRecognizer(recognizer: TextRecognizer, image: InputImage): String =
        suspendCancellableCoroutine { cont ->
            recognizer.process(image)
                .addOnSuccessListener { result ->
                    val text = result.textBlocks.joinToString(separator = "\n") { it.text }.trim()
                    cont.resume(text)
                }
                .addOnFailureListener { e -> cont.resumeWithException(e) }
        }

    override fun close() {
        latin.close()
        chinese.close()
    }
}
