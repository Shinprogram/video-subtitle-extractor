package com.shinprogram.subextract.domain.model

import kotlinx.serialization.Serializable

/**
 * A single subtitle cue.
 *
 * Times are in milliseconds from the start of the video.
 */
@Serializable
data class Subtitle(
    val startMs: Long,
    val endMs: Long,
    val text: String,
) {
    val durationMs: Long get() = (endMs - startMs).coerceAtLeast(0L)

    fun overlaps(otherStart: Long, otherEnd: Long): Boolean =
        startMs <= otherEnd && otherStart <= endMs
}

/** A full subtitle track associated with a source video. */
@Serializable
data class SubtitleTrack(
    val id: Long = 0L,
    val sourceUri: String,
    val sourceName: String,
    val language: String = "auto",
    val cues: List<Subtitle> = emptyList(),
    val createdAtMs: Long = System.currentTimeMillis(),
)
