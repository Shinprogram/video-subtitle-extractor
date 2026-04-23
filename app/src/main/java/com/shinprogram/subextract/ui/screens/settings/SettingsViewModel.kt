package com.shinprogram.subextract.ui.screens.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shinprogram.subextract.domain.repository.SettingsRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsUiState(
    val geminiApiKey: String = "",
    val targetLanguage: String = "en",
    val useGpu: Boolean = true,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val repo: SettingsRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repo.geminiApiKey.collect { k -> _state.update { it.copy(geminiApiKey = k) } }
        }
        viewModelScope.launch {
            repo.targetLanguage.collect { l -> _state.update { it.copy(targetLanguage = l) } }
        }
        viewModelScope.launch {
            repo.useGpu.collect { g -> _state.update { it.copy(useGpu = g) } }
        }
    }

    fun setGeminiKey(value: String) = viewModelScope.launch { repo.setGeminiApiKey(value) }
    fun setTargetLanguage(value: String) = viewModelScope.launch { repo.setTargetLanguage(value) }
    fun setUseGpu(value: Boolean) = viewModelScope.launch { repo.setUseGpu(value) }
}
