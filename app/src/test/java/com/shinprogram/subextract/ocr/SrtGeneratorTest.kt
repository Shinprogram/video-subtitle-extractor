package com.shinprogram.subextract.ocr

import com.shinprogram.subextract.domain.model.Subtitle
import org.junit.Assert.assertEquals
import org.junit.Test

class SrtGeneratorTest {
    @Test fun `formats a multi-cue track into valid SRT`() {
        val cues = listOf(
            Subtitle(0L, 1_500L, "Hello world"),
            Subtitle(2_000L, 4_321L, "Second line"),
        )
        val srt = SrtGenerator.build(cues)
        val expected = """
            1
            00:00:00,000 --> 00:00:01,500
            Hello world

            2
            00:00:02,000 --> 00:00:04,321
            Second line


        """.trimIndent()
        assertEquals(expected, srt)
    }

    @Test fun `empty list produces empty output`() {
        assertEquals("", SrtGenerator.build(emptyList()))
    }
}
