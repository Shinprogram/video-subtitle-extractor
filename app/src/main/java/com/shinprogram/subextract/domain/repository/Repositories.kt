package com.shinprogram.subextract.domain.repository

import android.net.Uri
import com.shinprogram.subextract.domain.model.Subtitle
import com.shinprogram.subextract.domain.model.SubtitleTrack
import kotlinx.coroutines.flow.Flow

/** Progress callback emitted while a long-running OCR job is running. */
data class ExtractionProgress(
    val processedFrames: Int,
    val totalFrames: Int,
    val cuesSoFar: Int,
    val currentMs: Long,
    val done: Boolean = false,
) {
    val ratio: Float
        get() = if (totalFrames <= 0) 0f else processedFrames.toFloat() / totalFrames
}

interface SubtitleExtractorRepository {
    /**
     * Streams [ExtractionProgress] while processing [videoUri]. The final item in
     * the flow has [ExtractionProgress.done] = true and contains all cues in
     * [ExtractionProgress.cuesSoFar].
     */
    fun extract(videoUri: Uri, opts: ExtractionOptions = ExtractionOptions()): Flow<ExtractionProgress>

    /** Returns the most recently extracted cues. */
    suspend fun lastCues(): List<Subtitle>
}

data class ExtractionOptions(
    /** Frames sampled per second of video. 2.0 gives a good quality/speed balance. */
    val framesPerSecond: Float = 2f,
    /**
     * Fraction of the frame (from the bottom) that is cropped before OCR.
     * 0.33 matches the typical "lower third" placement of burned-in subtitles.
     */
    val bottomCropFraction: Float = 0.33f,
    /** Minimum cue duration, in ms. Very short flashes are ignored. */
    val minCueDurationMs: Long = 200L,
    /** Gap, in ms, under which two consecutive identical cues are merged. */
    val mergeGapMs: Long = 400L,
    /** Similarity threshold used when deduplicating consecutive frames. */
    val dedupSimilarity: Float = 0.80f,
    /** Force use of a specific OCR engine; null picks the best available. */
    val preferredEngine: String? = null,
)

interface SubtitleTrackRepository {
    fun observeAll(): Flow<List<SubtitleTrack>>
    suspend fun get(id: Long): SubtitleTrack?
    suspend fun save(track: SubtitleTrack): Long
    suspend fun delete(id: Long)
}

interface TranslationRepository {
    /** Translates each cue's text to [targetLanguage]. */
    suspend fun translate(cues: List<Subtitle>, targetLanguage: String): Result<List<Subtitle>>
}

interface SettingsRepository {
    val geminiApiKey: Flow<String>
    suspend fun setGeminiApiKey(value: String)

    val targetLanguage: Flow<String>
    suspend fun setTargetLanguage(value: String)

    val useGpu: Flow<Boolean>
    suspend fun setUseGpu(value: Boolean)
}
