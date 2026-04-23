package com.shinprogram.subextract.work

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import com.shinprogram.subextract.R
import com.shinprogram.subextract.domain.repository.ExtractionOptions
import com.shinprogram.subextract.domain.repository.SubtitleExtractorRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import kotlinx.coroutines.flow.collectLatest

/**
 * Long-running OCR job. We run as a foreground service so Android doesn't kill
 * the pipeline halfway through on low-memory devices.
 */
@HiltWorker
class OcrWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
    private val extractor: SubtitleExtractorRepository,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val uriStr = inputData.getString(KEY_URI) ?: return Result.failure()
        setForeground(createForegroundInfo(applicationContext, 0, 0))
        val opts = ExtractionOptions(
            framesPerSecond = inputData.getFloat(KEY_FPS, 2f),
            bottomCropFraction = inputData.getFloat(KEY_CROP, 0.33f),
        )
        var finalCues = 0
        extractor.extract(Uri.parse(uriStr), opts).collectLatest { progress ->
            finalCues = progress.cuesSoFar
            setForeground(createForegroundInfo(applicationContext, progress.processedFrames, progress.totalFrames))
            setProgress(
                Data.Builder()
                    .putInt(PROGRESS_PROCESSED, progress.processedFrames)
                    .putInt(PROGRESS_TOTAL, progress.totalFrames)
                    .putInt(PROGRESS_CUES, progress.cuesSoFar)
                    .putBoolean(PROGRESS_DONE, progress.done)
                    .build(),
            )
        }
        return Result.success(Data.Builder().putInt(PROGRESS_CUES, finalCues).build())
    }

    private fun createForegroundInfo(ctx: Context, processed: Int, total: Int): ForegroundInfo {
        val channelId = ensureChannel(ctx)
        val percent = if (total > 0) ((processed * 100f) / total).toInt() else 0
        val notification = NotificationCompat.Builder(ctx, channelId)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle(ctx.getString(R.string.extracting_subtitles))
            .setContentText(ctx.getString(R.string.extracting_progress_template, processed, total))
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setProgress(total.coerceAtLeast(1), processed, total <= 0)
            .setSubText("$percent%")
            .build()
        val fgType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q)
            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC else 0
        return ForegroundInfo(NOTIFICATION_ID, notification, fgType)
    }

    private fun ensureChannel(ctx: Context): String {
        val id = "ocr_channel"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val mgr = ctx.getSystemService(NotificationManager::class.java)
            if (mgr.getNotificationChannel(id) == null) {
                mgr.createNotificationChannel(
                    NotificationChannel(id, "Subtitle extraction", NotificationManager.IMPORTANCE_LOW)
                )
            }
        }
        return id
    }

    companion object {
        const val KEY_URI = "video_uri"
        const val KEY_FPS = "fps"
        const val KEY_CROP = "crop"
        const val PROGRESS_PROCESSED = "processed"
        const val PROGRESS_TOTAL = "total"
        const val PROGRESS_CUES = "cues"
        const val PROGRESS_DONE = "done"
        private const val NOTIFICATION_ID = 2001
    }
}
