package com.shinprogram.subextract.ui.screens.editor

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CallMerge
import androidx.compose.material.icons.filled.CallSplit
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.FileDownload
import androidx.compose.material.icons.filled.Translate
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.shinprogram.subextract.domain.model.Subtitle
import kotlinx.coroutines.launch
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EditorScreen(
    onBack: () -> Unit,
    vm: EditorViewModel = hiltViewModel(),
) {
    val state by vm.state.collectAsStateWithLifecycle()
    val snackbarHost = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    val exportLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/x-subrip")
    ) { uri ->
        uri ?: return@rememberLauncherForActivityResult
        vm.exportSrt(uri)
    }

    LaunchedEffect(state.snackbar) {
        state.snackbar?.let {
            snackbarHost.showSnackbar(it)
            vm.clearSnackbar()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Edit subtitles") },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back") }
                },
                actions = {
                    IconButton(onClick = { exportLauncher.launch("subtitles.srt") }) {
                        Icon(Icons.Filled.FileDownload, contentDescription = "Export SRT")
                    }
                    IconButton(onClick = { vm.translate() }) {
                        Icon(Icons.Filled.Translate, contentDescription = "Translate")
                    }
                },
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = vm::add) { Icon(Icons.Filled.Add, contentDescription = "Add") }
        },
        snackbarHost = { SnackbarHost(snackbarHost) },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            if (state.isTranslating) {
                Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator()
                    Spacer(Modifier.height(0.dp))
                    Text("  Translating…")
                }
            }
            LazyColumn(
                contentPadding = androidx.compose.foundation.layout.PaddingValues(12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                itemsIndexed(state.cues, key = { idx, _ -> idx }) { idx, cue ->
                    CueCard(
                        index = idx,
                        cue = cue,
                        selected = state.selected == idx,
                        onSelect = { vm.select(idx) },
                        onTextChange = { vm.updateCue(idx, text = it) },
                        onStartChange = { vm.updateCue(idx, startMs = it) },
                        onEndChange = { vm.updateCue(idx, endMs = it) },
                        onSplit = { vm.split(idx) },
                        onMerge = { vm.mergeWithNext(idx) },
                        onDelete = { vm.delete(idx) },
                    )
                }
            }
        }
    }
}

@Composable
private fun CueCard(
    index: Int,
    cue: Subtitle,
    selected: Boolean,
    onSelect: () -> Unit,
    onTextChange: (String) -> Unit,
    onStartChange: (Long) -> Unit,
    onEndChange: (Long) -> Unit,
    onSplit: () -> Unit,
    onMerge: () -> Unit,
    onDelete: () -> Unit,
) {
    Card(
        onClick = onSelect,
        modifier = Modifier.fillMaxWidth(),
        colors = if (selected) CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)
        else CardDefaults.cardColors(),
        shape = RoundedCornerShape(12.dp),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("#${index + 1}", style = MaterialTheme.typography.labelLarge)
                Spacer(Modifier.fillMaxWidth(0.02f))
                TimeField(
                    label = "Start",
                    valueMs = cue.startMs,
                    onChange = onStartChange,
                    modifier = Modifier.fillMaxWidth(0.42f),
                )
                Spacer(Modifier.fillMaxWidth(0.02f))
                TimeField(
                    label = "End",
                    valueMs = cue.endMs,
                    onChange = onEndChange,
                    modifier = Modifier.fillMaxWidth(0.42f),
                )
            }
            OutlinedTextField(
                value = cue.text,
                onValueChange = onTextChange,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("Text") },
                minLines = 2,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                AssistChip(onClick = onSplit, label = { Text("Split") }, leadingIcon = { Icon(Icons.Filled.CallSplit, null) })
                AssistChip(onClick = onMerge, label = { Text("Merge") }, leadingIcon = { Icon(Icons.Filled.CallMerge, null) })
                AssistChip(onClick = onDelete, label = { Text("Delete") }, leadingIcon = { Icon(Icons.Filled.Delete, null) })
            }
        }
    }
}

@Composable
private fun TimeField(
    label: String,
    valueMs: Long,
    onChange: (Long) -> Unit,
    modifier: Modifier = Modifier,
) {
    OutlinedTextField(
        value = formatMs(valueMs),
        onValueChange = { text ->
            parseMs(text)?.let(onChange)
        },
        label = { Text(label) },
        singleLine = true,
        modifier = modifier,
    )
}

private fun formatMs(ms: Long): String {
    val hours = ms / 3_600_000
    val minutes = (ms / 60_000) % 60
    val seconds = (ms / 1_000) % 60
    val millis = ms % 1_000
    return String.format(Locale.ROOT, "%02d:%02d:%02d.%03d", hours, minutes, seconds, millis)
}

private fun parseMs(text: String): Long? {
    val normalised = text.trim().replace(',', '.')
    val regex = Regex("""^(\d{1,2}):(\d{1,2}):(\d{1,2})[.](\d{1,3})$""")
    val m = regex.matchEntire(normalised) ?: return null
    val (h, mnt, s, ms) = m.destructured
    val millis = ms.padEnd(3, '0').take(3)
    return h.toLong() * 3_600_000 + mnt.toLong() * 60_000 + s.toLong() * 1_000 + millis.toLong()
}
