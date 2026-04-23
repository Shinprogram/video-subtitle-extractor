package com.shinprogram.subextract.ui.screens.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    vm: SettingsViewModel = hiltViewModel(),
) {
    val state by vm.state.collectAsStateWithLifecycle()
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back") }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("Translation", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = state.geminiApiKey,
                onValueChange = vm::setGeminiKey,
                label = { Text("Gemini API key") },
                supportingText = { Text("Paste a Google AI Studio key. Falls back to the one in local.properties.") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = state.targetLanguage,
                onValueChange = vm::setTargetLanguage,
                label = { Text("Target language") },
                supportingText = { Text("ISO 639-1 code (e.g. en, vi, es, zh-CN).") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            Text("OCR", style = MaterialTheme.typography.titleMedium)
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column(Modifier.fillMaxWidth(0.8f)) {
                    Text("Prefer GPU / NNAPI", style = MaterialTheme.typography.bodyLarge)
                    Text(
                        "Enables the OpenCL backend for Paddle Lite on Snapdragon SoCs. Falls back to CPU automatically.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                Switch(checked = state.useGpu, onCheckedChange = vm::setUseGpu)
            }
        }
    }
}
