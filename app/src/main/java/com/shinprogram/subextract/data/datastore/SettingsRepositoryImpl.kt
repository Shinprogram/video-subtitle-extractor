package com.shinprogram.subextract.data.datastore

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.shinprogram.subextract.BuildConfig
import com.shinprogram.subextract.domain.repository.SettingsRepository
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore by preferencesDataStore(name = "subextract_settings")

@Singleton
class SettingsRepositoryImpl @Inject constructor(
    @ApplicationContext private val context: Context,
) : SettingsRepository {

    private val store = context.dataStore

    override val geminiApiKey: Flow<String> = store.data.map { prefs ->
        // Runtime key takes priority; build-time key is the fallback.
        prefs[KEY_GEMINI].orEmpty().ifBlank { BuildConfig.GEMINI_API_KEY }
    }

    override suspend fun setGeminiApiKey(value: String) {
        store.edit { it[KEY_GEMINI] = value.trim() }
    }

    override val targetLanguage: Flow<String> = store.data.map { it[KEY_LANG] ?: "en" }
    override suspend fun setTargetLanguage(value: String) {
        store.edit { it[KEY_LANG] = value }
    }

    override val useGpu: Flow<Boolean> = store.data.map { it[KEY_GPU] ?: true }
    override suspend fun setUseGpu(value: Boolean) {
        store.edit { it[KEY_GPU] = value }
    }

    private companion object {
        val KEY_GEMINI = stringPreferencesKey("gemini_api_key")
        val KEY_LANG = stringPreferencesKey("target_language")
        val KEY_GPU = booleanPreferencesKey("use_gpu")
    }
}
