package com.shinprogram.subextract.ocr

import android.content.Context
import android.graphics.Bitmap
import android.net.Uri
import com.shinprogram.subextract.domain.model.Subtitle
import com.shinprogram.subextract.domain.repository.ExtractionOptions
import com.shinprogram.subextract.domain.repository.ExtractionProgress
import com.shinprogram.subextract.domain.repository.SubtitleExtractorRepository
import com.shinprogram.subextract.ocr.paddle.PaddleOcrEngine
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import javax.inject.Inject
import javax.inject.Singleton

/**
 * The top-level extraction pipeline.
 *
 * ```
 * Video ─▶ plan ─▶ decode scaled frame ─▶ crop lower 1/3 ─▶ OCR ─▶
 *         clean ─▶ de-dup consecutive ─▶ merge runs ─▶ List<Subtitle>
 * ```
 */
@Singleton
class SubtitleExtractor @Inject constructor(
    @ApplicationContext private val context: Context,
    private val sampler: FrameSampler,
    private val mlkit: MlKitOcrEngine,
    private val paddle: PaddleOcrEngine,
) : SubtitleExtractorRepository {

    @Volatile private var cached: List<Subtitle> = emptyList()

    override fun extract(videoUri: Uri, opts: ExtractionOptions): Flow<ExtractionProgress> = flow {
        val plan = sampler.plan(videoUri, opts.framesPerSecond)
        val engine = pickEngine(opts.preferredEngine)

        val runs = ArrayDeque<MutableRun>()
        var processed = 0
        for (frame in sampler.sample(videoUri, plan)) {
            val cropped = cropLowerThird(frame.bitmap, opts.bottomCropFraction)
            frame.bitmap.recycleIfDifferent(cropped)
            val raw = try {
                engine.recognize(cropped)
            } catch (t: Throwable) {
                ""
            } finally {
                cropped.recycleSafely()
            }
            val text = TextFilter.clean(raw)
            if (text.isNotEmpty()) {
                appendRun(runs, frame.timestampMs, text, opts)
            } else {
                closeStaleRuns(runs, frame.timestampMs, opts)
            }
            processed++
            emit(
                ExtractionProgress(
                    processedFrames = processed,
                    totalFrames = plan.timestamps.size,
                    cuesSoFar = runs.size,
                    currentMs = frame.timestampMs,
                )
            )
        }

        val cues = runs.map { it.toSubtitle(opts) }
            .filter { it.durationMs >= opts.minCueDurationMs }
            .sortedBy { it.startMs }
        cached = cues
        emit(
            ExtractionProgress(
                processedFrames = processed,
                totalFrames = plan.timestamps.size,
                cuesSoFar = cues.size,
                currentMs = plan.durationMs,
                done = true,
            )
        )
    }.flowOn(Dispatchers.Default)

    override suspend fun lastCues(): List<Subtitle> = cached

    private suspend fun pickEngine(preferred: String?): OcrEngine {
        val candidates = when (preferred) {
            "paddle" -> listOf(paddle, mlkit)
            "mlkit" -> listOf(mlkit)
            else -> listOf(paddle, mlkit)
        }
        return candidates.firstOrNull { it.isAvailable() } ?: mlkit
    }

    // ---- helpers ----------------------------------------------------------

    private class MutableRun(
        var startMs: Long,
        var endMs: Long,
        val samples: MutableList<String>,
    ) {
        fun toSubtitle(opts: ExtractionOptions): Subtitle {
            // Majority-voted text across samples.
            val text = samples.groupingBy { it }.eachCount().maxByOrNull { it.value }?.key
                ?: samples.last()
            val endPad = (1000f / 2f).toLong() // assume ~2fps sampling when padding
            return Subtitle(startMs = startMs, endMs = endMs + endPad, text = text)
        }
    }

    private fun appendRun(
        runs: ArrayDeque<MutableRun>,
        tsMs: Long,
        text: String,
        opts: ExtractionOptions,
    ) {
        val last = runs.lastOrNull()
        if (last != null && TextFilter.similarity(last.samples.last(), text) >= opts.dedupSimilarity) {
            last.endMs = tsMs
            last.samples.add(text)
            return
        }
        if (last != null && tsMs - last.endMs <= opts.mergeGapMs &&
            TextFilter.similarity(last.samples.last(), text) >= opts.dedupSimilarity
        ) {
            last.endMs = tsMs
            last.samples.add(text)
            return
        }
        runs.addLast(MutableRun(tsMs, tsMs, mutableListOf(text)))
    }

    private fun closeStaleRuns(
        runs: ArrayDeque<MutableRun>,
        tsMs: Long,
        opts: ExtractionOptions,
    ) {
        // Nothing to do for empty-text frames; the next non-empty frame that
        // starts a new run will naturally cap the previous run's endMs.
        // We keep the method to make the pipeline's intent explicit.
    }
}

/** Returns a new bitmap containing [fraction] of [src]'s height, counted from the bottom. */
internal fun cropLowerThird(src: Bitmap, fraction: Float): Bitmap {
    val h = (src.height * fraction).toInt().coerceAtLeast(1)
    val y = src.height - h
    return Bitmap.createBitmap(src, 0, y, src.width, h)
}

private fun Bitmap.recycleIfDifferent(other: Bitmap) {
    if (this !== other && !this.isRecycled) this.recycle()
}

private fun Bitmap.recycleSafely() {
    if (!isRecycled) recycle()
}
