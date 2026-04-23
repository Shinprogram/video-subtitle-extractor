package com.shinprogram.subextract.ui.screens.editor

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shinprogram.subextract.domain.model.Subtitle
import com.shinprogram.subextract.domain.repository.SettingsRepository
import com.shinprogram.subextract.domain.repository.TranslationRepository
import com.shinprogram.subextract.ocr.SrtGenerator
import com.shinprogram.subextract.ui.common.ActiveTrackHolder
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class EditorUiState(
    val cues: List<Subtitle> = emptyList(),
    val selected: Int = -1,
    val isTranslating: Boolean = false,
    val snackbar: String? = null,
)

@HiltViewModel
class EditorViewModel @Inject constructor(
    @ApplicationContext private val context: Context,
    private val activeTrack: ActiveTrackHolder,
    private val translation: TranslationRepository,
    private val settings: SettingsRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(EditorUiState())
    val state: StateFlow<EditorUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            activeTrack.cues.collect { cues ->
                _state.update { it.copy(cues = cues) }
            }
        }
    }

    fun select(index: Int) = _state.update { it.copy(selected = index) }

    fun updateCue(index: Int, text: String? = null, startMs: Long? = null, endMs: Long? = null) {
        val current = _state.value.cues.getOrNull(index) ?: return
        val updated = current.copy(
            text = text ?: current.text,
            startMs = startMs ?: current.startMs,
            endMs = endMs ?: current.endMs,
        )
        activeTrack.updateCue(index, updated)
    }

    fun split(index: Int) {
        val current = _state.value.cues.getOrNull(index) ?: return
        val mid = (current.startMs + current.endMs) / 2
        val leftText: String
        val rightText: String
        val splitAt = current.text.indexOf('\n').takeIf { it >= 0 }
        if (splitAt != null) {
            leftText = current.text.substring(0, splitAt).trim()
            rightText = current.text.substring(splitAt + 1).trim()
        } else {
            val halfWord = current.text.length / 2
            leftText = current.text.substring(0, halfWord).trim()
            rightText = current.text.substring(halfWord).trim()
        }
        activeTrack.updateCue(index, current.copy(endMs = mid, text = leftText))
        activeTrack.insertCue(Subtitle(startMs = mid + 1, endMs = current.endMs, text = rightText))
    }

    fun mergeWithNext(index: Int) {
        val cues = _state.value.cues
        val a = cues.getOrNull(index) ?: return
        val b = cues.getOrNull(index + 1) ?: return
        val merged = Subtitle(a.startMs, b.endMs, listOf(a.text, b.text).joinToString(" ").trim())
        activeTrack.updateCue(index, merged)
        activeTrack.removeCue(index + 1)
    }

    fun delete(index: Int) = activeTrack.removeCue(index)

    fun add() {
        val last = _state.value.cues.lastOrNull()
        val start = last?.endMs?.plus(500L) ?: 0L
        activeTrack.insertCue(Subtitle(start, start + 2_000L, "New line"))
    }

    fun exportSrt(uri: Uri): Result<Int> = runCatching {
        val srt = SrtGenerator.build(_state.value.cues)
        context.contentResolver.openOutputStream(uri, "wt").use { out ->
            requireNotNull(out) { "Could not open output stream" }.write(srt.toByteArray(Charsets.UTF_8))
        }
        _state.update { it.copy(snackbar = "Exported ${_state.value.cues.size} cues.") }
        _state.value.cues.size
    }

    fun translate(language: String? = null) {
        viewModelScope.launch {
            _state.update { it.copy(isTranslating = true, snackbar = null) }
            val target = language ?: settings.targetLanguage.first()
            translation.translate(_state.value.cues, target)
                .onSuccess { cues ->
                    activeTrack.replaceAll(cues)
                    _state.update { it.copy(isTranslating = false, snackbar = "Translated to $target.") }
                }
                .onFailure { t ->
                    _state.update { it.copy(isTranslating = false, snackbar = "Translation failed: ${t.message}") }
                }
        }
    }

    fun clearSnackbar() = _state.update { it.copy(snackbar = null) }
}
