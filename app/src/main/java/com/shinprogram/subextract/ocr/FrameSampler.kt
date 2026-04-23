package com.shinprogram.subextract.ocr

import android.content.Context
import android.graphics.Bitmap
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Build
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/** A single decoded frame with its timestamp. */
data class SampledFrame(val timestampMs: Long, val bitmap: Bitmap)

/**
 * Extracts frames from a video using the system's [MediaMetadataRetriever].
 *
 * We prefer [MediaMetadataRetriever.getScaledFrameAtTime] — it does the
 * downscale inside the decoder, avoiding an expensive full-resolution bitmap
 * allocation per frame.
 */
@Singleton
class FrameSampler @Inject constructor(
    @ApplicationContext private val context: Context,
) {

    data class Plan(
        val durationMs: Long,
        val timestamps: List<Long>,
        val frameWidth: Int,
        val frameHeight: Int,
    )

    /** Chooses sample timestamps for [uri] given [fps] frames per second. */
    fun plan(uri: Uri, fps: Float): Plan {
        require(fps > 0f) { "fps must be positive" }
        val mmr = MediaMetadataRetriever()
        try {
            mmr.setDataSource(context, uri)
            val duration = mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull() ?: 0L
            val width = mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)?.toIntOrNull() ?: 0
            val height = mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)?.toIntOrNull() ?: 0
            val stepMs = (1000f / fps).toLong().coerceAtLeast(1L)
            val stamps = buildList {
                var t = 0L
                while (t < duration) {
                    add(t)
                    t += stepMs
                }
            }
            return Plan(duration, stamps, width, height)
        } finally {
            mmr.release()
        }
    }

    /**
     * Yields sampled frames lazily. The caller is responsible for recycling the
     * returned bitmaps once the OCR engine has consumed them.
     */
    fun sample(uri: Uri, plan: Plan, targetWidth: Int = 960): Sequence<SampledFrame> = sequence {
        val mmr = MediaMetadataRetriever()
        try {
            mmr.setDataSource(context, uri)
            // Scale down to a manageable width; aspect ratio preserved by the retriever.
            val outW = targetWidth.coerceAtMost(plan.frameWidth.takeIf { it > 0 } ?: targetWidth)
            val ratio = if (plan.frameWidth > 0) plan.frameHeight.toFloat() / plan.frameWidth else 9f / 16f
            val outH = (outW * ratio).toInt().coerceAtLeast(1)
            for (t in plan.timestamps) {
                val bmp = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
                    mmr.getScaledFrameAtTime(
                        t * 1000L,
                        MediaMetadataRetriever.OPTION_CLOSEST_SYNC,
                        outW, outH,
                    )
                } else {
                    // API 24–26 fallback: decode at full resolution and scale on the
                    // CPU. The native downscale API only exists from O_MR1 onward.
                    mmr.getFrameAtTime(t * 1000L, MediaMetadataRetriever.OPTION_CLOSEST_SYNC)
                        ?.let { Bitmap.createScaledBitmap(it, outW, outH, true) }
                } ?: continue
                yield(SampledFrame(t, bmp))
            }
        } finally {
            mmr.release()
        }
    }
}
