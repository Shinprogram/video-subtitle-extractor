package com.shinprogram.subextract.ui.common

import android.net.Uri
import com.shinprogram.subextract.domain.model.Subtitle
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Hot state shared between the Player and Editor screens. Kept singleton-scoped
 * so the user can jump between screens without losing the active track.
 *
 * In a larger app this would be backed by the database and keyed by track id,
 * but for the demo we only ever have one active track at a time.
 */
@Singleton
class ActiveTrackHolder @Inject constructor() {
    private val _videoUri = MutableStateFlow<Uri?>(null)
    val videoUri: StateFlow<Uri?> = _videoUri.asStateFlow()

    private val _cues = MutableStateFlow<List<Subtitle>>(emptyList())
    val cues: StateFlow<List<Subtitle>> = _cues.asStateFlow()

    fun setVideo(uri: Uri?) { _videoUri.value = uri }
    fun setCues(list: List<Subtitle>) { _cues.value = list.sortedBy { it.startMs } }
    fun updateCue(index: Int, cue: Subtitle) {
        val current = _cues.value.toMutableList()
        if (index in current.indices) {
            current[index] = cue
            _cues.value = current.sortedBy { it.startMs }
        }
    }
    fun insertCue(cue: Subtitle) {
        _cues.value = (_cues.value + cue).sortedBy { it.startMs }
    }
    fun removeCue(index: Int) {
        val current = _cues.value.toMutableList()
        if (index in current.indices) {
            current.removeAt(index)
            _cues.value = current
        }
    }
    fun replaceAll(list: List<Subtitle>) { setCues(list) }
}
