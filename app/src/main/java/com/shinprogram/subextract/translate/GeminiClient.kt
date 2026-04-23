package com.shinprogram.subextract.translate

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import retrofit2.http.Body
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Minimal Gemini REST client used for subtitle translation.
 *
 * We request plain-text output so the response can be parsed line-by-line
 * without any additional JSON handling on the client side.
 */
interface GeminiService {
    @POST("v1beta/models/{model}:generateContent")
    suspend fun generate(
        @Path("model") model: String,
        @Query("key") apiKey: String,
        @Body request: GenerateContentRequest,
    ): GenerateContentResponse
}

@Serializable
data class GenerateContentRequest(
    val contents: List<Content>,
    val generationConfig: GenerationConfig = GenerationConfig(),
    val safetySettings: List<SafetySetting> = emptyList(),
)

@Serializable
data class Content(
    val role: String = "user",
    val parts: List<Part>,
)

@Serializable
data class Part(val text: String)

@Serializable
data class GenerationConfig(
    val temperature: Float = 0.2f,
    val topK: Int = 32,
    val topP: Float = 0.95f,
    @SerialName("maxOutputTokens") val maxOutputTokens: Int = 4096,
    @SerialName("responseMimeType") val responseMimeType: String = "text/plain",
)

@Serializable
data class SafetySetting(val category: String, val threshold: String)

@Serializable
data class GenerateContentResponse(
    val candidates: List<Candidate> = emptyList(),
) {
    val firstText: String
        get() = candidates.firstOrNull()?.content?.parts?.joinToString(separator = "") { it.text }.orEmpty()
}

@Serializable
data class Candidate(val content: Content? = null, val finishReason: String? = null)
