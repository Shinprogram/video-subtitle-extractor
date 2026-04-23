package com.shinprogram.subextract.translate

import com.shinprogram.subextract.domain.model.Subtitle
import com.shinprogram.subextract.domain.repository.SettingsRepository
import com.shinprogram.subextract.domain.repository.TranslationRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Translates subtitles using Gemini. We chunk the cues so we never exceed the
 * per-request token budget and so that one failed chunk doesn't discard the
 * entire translation.
 */
@Singleton
class TranslationRepositoryImpl @Inject constructor(
    private val service: GeminiService,
    private val settings: SettingsRepository,
) : TranslationRepository {

    private val model = "gemini-1.5-flash-latest"
    private val chunkSize = 40

    override suspend fun translate(
        cues: List<Subtitle>,
        targetLanguage: String,
    ): Result<List<Subtitle>> = withContext(Dispatchers.IO) {
        val key = settings.geminiApiKey.first()
        if (key.isBlank()) {
            return@withContext Result.failure(IllegalStateException("Gemini API key is not configured."))
        }
        runCatching {
            val out = ArrayList<Subtitle>(cues.size)
            for (chunk in cues.chunked(chunkSize)) {
                val translated = translateChunk(chunk, targetLanguage, key)
                out.addAll(translated)
            }
            out
        }
    }

    private suspend fun translateChunk(
        chunk: List<Subtitle>,
        target: String,
        apiKey: String,
    ): List<Subtitle> {
        val prompt = buildString {
            appendLine("You are a professional subtitle translator.")
            appendLine("Translate each numbered line into $target.")
            appendLine("Return ONLY the translations, one per line, in the same order, with the same numbering. Do not add commentary.")
            appendLine()
            chunk.forEachIndexed { idx, cue ->
                append(idx + 1).append(". ").append(cue.text.replace("\n", " ")).append('\n')
            }
        }
        val req = GenerateContentRequest(
            contents = listOf(Content(parts = listOf(Part(prompt))))
        )
        val resp = service.generate(model, apiKey, req)
        val text = resp.firstText
        val translatedLines = parseNumbered(text, chunk.size)
        return chunk.mapIndexed { idx, cue ->
            cue.copy(text = translatedLines.getOrNull(idx)?.takeIf { it.isNotBlank() } ?: cue.text)
        }
    }

    private fun parseNumbered(text: String, expected: Int): List<String> {
        // Accepts lines like "1. Foo", "1) Foo", "1: Foo".
        val regex = Regex("""^\s*(\d+)[.):\-\s]+(.*)$""")
        val ordered = arrayOfNulls<String>(expected)
        for (line in text.lineSequence()) {
            val m = regex.matchEntire(line.trim()) ?: continue
            val idx = (m.groupValues[1].toIntOrNull() ?: continue) - 1
            if (idx in 0 until expected) ordered[idx] = m.groupValues[2].trim()
        }
        return ordered.map { it.orEmpty() }
    }
}
