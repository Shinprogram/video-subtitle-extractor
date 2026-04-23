package com.shinprogram.subextract.data.db

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(tableName = "subtitle_tracks")
data class SubtitleTrackEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0L,
    val sourceUri: String,
    val sourceName: String,
    val language: String,
    val createdAtMs: Long,
)

@Entity(
    tableName = "subtitle_cues",
    foreignKeys = [
        ForeignKey(
            entity = SubtitleTrackEntity::class,
            parentColumns = ["id"],
            childColumns = ["trackId"],
            onDelete = ForeignKey.CASCADE,
        ),
    ],
    indices = [Index("trackId")],
)
data class SubtitleCueEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0L,
    val trackId: Long,
    val startMs: Long,
    val endMs: Long,
    val text: String,
)
