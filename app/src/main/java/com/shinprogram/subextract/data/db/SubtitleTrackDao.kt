package com.shinprogram.subextract.data.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

@Dao
interface SubtitleTrackDao {
    @Query("SELECT * FROM subtitle_tracks ORDER BY createdAtMs DESC")
    fun observeAll(): Flow<List<SubtitleTrackEntity>>

    @Query("SELECT * FROM subtitle_tracks WHERE id = :id")
    suspend fun getTrack(id: Long): SubtitleTrackEntity?

    @Query("SELECT * FROM subtitle_cues WHERE trackId = :trackId ORDER BY startMs ASC")
    suspend fun getCues(trackId: Long): List<SubtitleCueEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertTrack(track: SubtitleTrackEntity): Long

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertCues(cues: List<SubtitleCueEntity>)

    @Query("DELETE FROM subtitle_cues WHERE trackId = :trackId")
    suspend fun clearCues(trackId: Long)

    @Query("DELETE FROM subtitle_tracks WHERE id = :id")
    suspend fun deleteTrack(id: Long)

    @Transaction
    suspend fun replaceTrack(track: SubtitleTrackEntity, cues: List<SubtitleCueEntity>): Long {
        val id = insertTrack(track)
        clearCues(id)
        insertCues(cues.map { it.copy(trackId = id) })
        return id
    }
}
