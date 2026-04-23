package com.shinprogram.subextract.ocr

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TextFilterTest {
    @Test fun `collapses whitespace`() {
        assertEquals("hello world", TextFilter.clean("  hello   world\n"))
    }

    @Test fun `drops pure punctuation and very short results`() {
        assertEquals("", TextFilter.clean("."))
        assertEquals("", TextFilter.clean("!!!"))
        assertEquals("", TextFilter.clean("a"))
    }

    @Test fun `similarity treats identical strings as 1`() {
        assertEquals(1f, TextFilter.similarity("hello", "hello"), 0.0001f)
    }

    @Test fun `similarity of different strings is below threshold`() {
        assertTrue(TextFilter.similarity("abcdef", "xyz123") < 0.5f)
    }

    @Test fun `similarity of near-duplicates is above threshold`() {
        assertTrue(TextFilter.similarity("Hello world", "Hello word") > 0.8f)
    }
}
