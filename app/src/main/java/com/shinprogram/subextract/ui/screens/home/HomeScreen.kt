package com.shinprogram.subextract.ui.screens.home

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.VideoFile
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onOpenSettings: () -> Unit,
    onVideoPicked: (Uri) -> Unit,
    vm: HomeViewModel = hiltViewModel(),
) {
    val state by vm.state.collectAsStateWithLifecycle()
    val pickVideo = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        uri ?: return@rememberLauncherForActivityResult
        vm.onVideoPicked(uri)
        onVideoPicked(uri)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("SubExtract") },
                actions = {
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Filled.Settings, contentDescription = "Settings")
                    }
                },
            )
        },
    ) { padding ->
        HomeBody(
            padding = padding,
            state = state,
            onPickVideo = { pickVideo.launch(arrayOf("video/*")) },
            onRecentPicked = onVideoPicked,
        )
    }
}

@Composable
private fun HomeBody(
    padding: PaddingValues,
    state: HomeUiState,
    onPickVideo: () -> Unit,
    onRecentPicked: (Uri) -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
        ) {
            Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Extract subtitles from any video", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                Text(
                    "Pick a video from your device. We'll sample frames, run OCR on the lower third of each frame, and build an editable subtitle track.",
                    style = MaterialTheme.typography.bodyMedium,
                )
                Button(onClick = onPickVideo, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Filled.VideoFile, contentDescription = null)
                    Text("  Pick a video")
                }
            }
        }

        if (state.recentPicks.isNotEmpty()) {
            Text("Recent", style = MaterialTheme.typography.titleMedium)
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(state.recentPicks) { uri ->
                    Card(
                        onClick = { onRecentPicked(uri) },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Box(Modifier.padding(16.dp)) {
                            Column {
                                Icon(Icons.Filled.History, contentDescription = null)
                                Text(uri.lastPathSegment ?: uri.toString(), style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                    }
                }
            }
        }
    }
}
