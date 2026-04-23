package com.shinprogram.subextract.ocr

import com.shinprogram.subextract.domain.model.Subtitle
import java.util.Locale

/** Generates SRT-formatted strings from a list of [Subtitle]. */
object SrtGenerator {

    fun build(cues: List<Subtitle>): String {
        if (cues.isEmpty()) return ""
        val sb = StringBuilder()
        cues.forEachIndexed { index, cue ->
            sb.append(index + 1).append('\n')
            sb.append(formatTime(cue.startMs)).append(" --> ").append(formatTime(cue.endMs)).append('\n')
            sb.append(cue.text.trim()).append("\n\n")
        }
        return sb.toString()
    }

    private fun formatTime(ms: Long): String {
        val hours = ms / 3_600_000
        val minutes = (ms / 60_000) % 60
        val seconds = (ms / 1_000) % 60
        val millis = ms % 1_000
        return String.format(Locale.ROOT, "%02d:%02d:%02d,%03d", hours, minutes, seconds, millis)
    }
}
