package com.shinprogram.subextract.ui.screens.player

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shinprogram.subextract.domain.model.Subtitle
import com.shinprogram.subextract.domain.repository.ExtractionOptions
import com.shinprogram.subextract.domain.repository.ExtractionProgress
import com.shinprogram.subextract.domain.repository.SubtitleExtractorRepository
import com.shinprogram.subextract.ui.common.ActiveTrackHolder
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class PlayerUiState(
    val isExtracting: Boolean = false,
    val progress: ExtractionProgress? = null,
    val positionMs: Long = 0L,
    val durationMs: Long = 0L,
    val cues: List<Subtitle> = emptyList(),
    val activeCueIndex: Int = -1,
    val errorMessage: String? = null,
)

@HiltViewModel
class PlayerViewModel @Inject constructor(
    private val extractor: SubtitleExtractorRepository,
    private val activeTrack: ActiveTrackHolder,
) : ViewModel() {

    private val _state = MutableStateFlow(PlayerUiState())
    val state: StateFlow<PlayerUiState> = _state.asStateFlow()

    private var extractJob: Job? = null

    init {
        viewModelScope.launch {
            activeTrack.cues.collectLatest { cues ->
                _state.update { it.copy(cues = cues, activeCueIndex = findCueIndex(cues, it.positionMs)) }
            }
        }
    }

    fun onPlayerReady(durationMs: Long) {
        _state.update { it.copy(durationMs = durationMs) }
    }

    fun onPositionUpdate(positionMs: Long) {
        _state.update { it.copy(positionMs = positionMs, activeCueIndex = findCueIndex(it.cues, positionMs)) }
    }

    fun startExtraction(videoUri: Uri, opts: ExtractionOptions = ExtractionOptions()) {
        extractJob?.cancel()
        _state.update { it.copy(isExtracting = true, progress = null, errorMessage = null) }
        extractJob = viewModelScope.launch {
            runCatching {
                extractor.extract(videoUri, opts).collect { progress ->
                    _state.update { it.copy(progress = progress, isExtracting = !progress.done) }
                    if (progress.done) {
                        val cues = extractor.lastCues()
                        activeTrack.setCues(cues)
                    }
                }
            }.onFailure { t ->
                _state.update { it.copy(isExtracting = false, errorMessage = t.message ?: "Extraction failed") }
            }
        }
    }

    fun cancelExtraction() {
        extractJob?.cancel()
        _state.update { it.copy(isExtracting = false) }
    }

    private fun findCueIndex(cues: List<Subtitle>, positionMs: Long): Int {
        if (cues.isEmpty()) return -1
        var lo = 0
        var hi = cues.size - 1
        while (lo <= hi) {
            val mid = (lo + hi) / 2
            val c = cues[mid]
            when {
                positionMs < c.startMs -> hi = mid - 1
                positionMs > c.endMs -> lo = mid + 1
                else -> return mid
            }
        }
        return -1
    }
}
