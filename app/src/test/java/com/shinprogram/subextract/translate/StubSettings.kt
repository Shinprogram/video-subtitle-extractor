package com.shinprogram.subextract.translate

import com.shinprogram.subextract.domain.repository.SettingsRepository
import kotlinx.coroutines.flow.MutableStateFlow

object StubSettings : SettingsRepository {
    override val geminiApiKey = MutableStateFlow("")
    override suspend fun setGeminiApiKey(value: String) { geminiApiKey.value = value }

    override val targetLanguage = MutableStateFlow("en")
    override suspend fun setTargetLanguage(value: String) { targetLanguage.value = value }

    override val useGpu = MutableStateFlow(true)
    override suspend fun setUseGpu(value: Boolean) { useGpu.value = value }
}
