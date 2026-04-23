package com.shinprogram.subextract.translate

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Exercises the numbered-list parser used to line up Gemini responses with the
 * original cues. Keeping this in its own test ensures we never regress the
 * ordering logic — mis-ordered translations would be very hard to debug
 * post-hoc.
 */
class TranslationParseTest {

    private val repo: TranslationRepositoryImpl = TranslationRepositoryImpl(
        service = object : GeminiService {
            override suspend fun generate(
                model: String,
                apiKey: String,
                request: GenerateContentRequest,
            ): GenerateContentResponse = GenerateContentResponse()
        },
        settings = StubSettings,
    )

    @Test fun `parses well-formed numbered output`() {
        val text = """
            1. Hola mundo
            2. ¿Cómo estás?
            3. Adiós
        """.trimIndent()
        val parsed = invokePrivateParse(repo, text, 3)
        assertEquals(listOf("Hola mundo", "¿Cómo estás?", "Adiós"), parsed)
    }

    @Test fun `tolerates alternate delimiters`() {
        val text = """
            1) one
            2: two
            3 - three
        """.trimIndent()
        val parsed = invokePrivateParse(repo, text, 3)
        assertEquals(listOf("one", "two", "three"), parsed)
    }

    @Test fun `fills missing entries with empty strings`() {
        val text = """
            1. only the first
        """.trimIndent()
        val parsed = invokePrivateParse(repo, text, 3)
        assertEquals(listOf("only the first", "", ""), parsed)
    }

    private fun invokePrivateParse(target: TranslationRepositoryImpl, text: String, expected: Int): List<String> {
        val m = TranslationRepositoryImpl::class.java.getDeclaredMethod(
            "parseNumbered", String::class.java, Int::class.javaPrimitiveType,
        ).apply { isAccessible = true }
        @Suppress("UNCHECKED_CAST")
        return m.invoke(target, text, expected) as List<String>
    }
}
