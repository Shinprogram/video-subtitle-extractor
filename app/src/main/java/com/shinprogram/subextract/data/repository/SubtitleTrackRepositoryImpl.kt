package com.shinprogram.subextract.data.repository

import com.shinprogram.subextract.data.db.SubtitleCueEntity
import com.shinprogram.subextract.data.db.SubtitleTrackDao
import com.shinprogram.subextract.data.db.SubtitleTrackEntity
import com.shinprogram.subextract.domain.model.Subtitle
import com.shinprogram.subextract.domain.model.SubtitleTrack
import com.shinprogram.subextract.domain.repository.SubtitleTrackRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SubtitleTrackRepositoryImpl @Inject constructor(
    private val dao: SubtitleTrackDao,
) : SubtitleTrackRepository {

    override fun observeAll(): Flow<List<SubtitleTrack>> =
        dao.observeAll().map { list ->
            list.map { SubtitleTrack(id = it.id, sourceUri = it.sourceUri, sourceName = it.sourceName, language = it.language, cues = emptyList(), createdAtMs = it.createdAtMs) }
        }

    override suspend fun get(id: Long): SubtitleTrack? {
        val entity = dao.getTrack(id) ?: return null
        val cues = dao.getCues(id).map { Subtitle(it.startMs, it.endMs, it.text) }
        return SubtitleTrack(entity.id, entity.sourceUri, entity.sourceName, entity.language, cues, entity.createdAtMs)
    }

    override suspend fun save(track: SubtitleTrack): Long {
        val entity = SubtitleTrackEntity(
            id = track.id,
            sourceUri = track.sourceUri,
            sourceName = track.sourceName,
            language = track.language,
            createdAtMs = track.createdAtMs,
        )
        val cueEntities = track.cues.map { SubtitleCueEntity(trackId = track.id, startMs = it.startMs, endMs = it.endMs, text = it.text) }
        return dao.replaceTrack(entity, cueEntities)
    }

    override suspend fun delete(id: Long) {
        dao.deleteTrack(id)
    }
}
