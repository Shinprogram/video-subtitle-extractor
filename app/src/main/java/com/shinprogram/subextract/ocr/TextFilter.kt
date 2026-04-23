package com.shinprogram.subextract.ocr

import kotlin.math.max

/**
 * Heuristics used by the pipeline to clean individual OCR outputs and decide
 * whether two consecutive recognitions represent the same spoken line.
 */
object TextFilter {

    private val CONTROL_CHARS = Regex("[\\p{Cntrl}&&[^\n\r\t]]")
    private val MULTI_SPACE = Regex("[\\s\u00A0\u3000]+")
    private val TRAILING_PUNCT_ONLY = Regex("^[\\p{Punct}\\s]+$")

    /**
     * Cleans one raw OCR recognition. Returns an empty string when the text is
     * clearly noise (too short, only punctuation, huge CJK-to-Latin ratio).
     */
    fun clean(raw: String): String {
        if (raw.isBlank()) return ""
        var s = raw.replace(CONTROL_CHARS, " ")
        s = s.replace(MULTI_SPACE, " ").trim()
        if (s.length < 2) return ""
        if (TRAILING_PUNCT_ONLY.matches(s)) return ""
        return s
    }

    /** Normalized-edit-distance similarity in [0..1]. */
    fun similarity(a: String, b: String): Float {
        if (a.isEmpty() && b.isEmpty()) return 1f
        val dist = levenshtein(a, b)
        val denom = max(a.length, b.length).toFloat()
        return 1f - dist / denom
    }

    fun levenshtein(a: String, b: String): Int {
        if (a == b) return 0
        if (a.isEmpty()) return b.length
        if (b.isEmpty()) return a.length
        val prev = IntArray(b.length + 1) { it }
        val curr = IntArray(b.length + 1)
        for (i in 1..a.length) {
            curr[0] = i
            for (j in 1..b.length) {
                val cost = if (a[i - 1] == b[j - 1]) 0 else 1
                curr[j] = minOf(
                    curr[j - 1] + 1,
                    prev[j] + 1,
                    prev[j - 1] + cost,
                )
            }
            System.arraycopy(curr, 0, prev, 0, curr.size)
        }
        return prev[b.length]
    }
}
