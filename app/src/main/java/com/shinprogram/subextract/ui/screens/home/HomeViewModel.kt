package com.shinprogram.subextract.ui.screens.home

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.shinprogram.subextract.ui.common.ActiveTrackHolder
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class HomeUiState(val recentPicks: List<Uri> = emptyList())

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val activeTrack: ActiveTrackHolder,
) : ViewModel() {

    private val _state = MutableStateFlow(HomeUiState())
    val state = _state.asStateFlow()

    fun onVideoPicked(uri: Uri) {
        activeTrack.setVideo(uri)
        activeTrack.setCues(emptyList())
        viewModelScope.launch {
            _state.value = HomeUiState(recentPicks = (listOf(uri) + _state.value.recentPicks).distinct().take(5))
        }
    }
}
