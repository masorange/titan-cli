package io.github.masorange.titan.desktop.ui.components.diff

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.Card
import androidx.compose.material.MaterialTheme
import androidx.compose.material.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.OutputTimelineItemState
import io.github.masorange.titan.desktop.state.OutputVisualFormat
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun DiffOutputView(
    item: OutputTimelineItemState,
    modifier: Modifier = Modifier,
) {
    val summaryLines = item.metadata.summaryLines()
    val files = item.metadata.diffFiles()
    val neutralColor = MaterialTheme.colors.onSurface.copy(alpha = 0.85f)
    val preview = remember(item.content) { buildDiffPreview(item.content) }

    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(Spacing.s4),
    ) {
        if (summaryLines.isNotEmpty()) {
            Column(verticalArrangement = Arrangement.spacedBy(Spacing.s2)) {
                summaryLines.forEach { line ->
                    Text(
                        text = line,
                        style = MaterialTheme.typography.body2,
                        color = MaterialTheme.colors.onSurface.copy(alpha = 0.8f),
                    )
                }
            }
        }

        if (files.isNotEmpty()) {
            Column(verticalArrangement = Arrangement.spacedBy(Spacing.s2)) {
                files.forEach { file ->
                    Row(horizontalArrangement = Arrangement.spacedBy(Spacing.s3)) {
                        Text(file.path, style = MaterialTheme.typography.body2)
                        Text(
                            text = "+${file.additions}",
                            style = MaterialTheme.typography.caption,
                            color = Color(0xFF2E7D32),
                        )
                        Text(
                            text = "-${file.deletions}",
                            style = MaterialTheme.typography.caption,
                            color = Color(0xFFC62828),
                        )
                    }
                }
            }
        }

        if (preview.lines.isNotEmpty()) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFFF6F8FA))
                    .padding(Spacing.s4),
                verticalArrangement = Arrangement.spacedBy(Spacing.s1),
            ) {
                preview.lines.forEach { line ->
                    Text(
                        text = line.text,
                        style = MaterialTheme.typography.caption,
                        fontFamily = FontFamily.Monospace,
                        color = line.color,
                    )
                }

                if (preview.truncated) {
                    Text(
                        text = "Preview truncated for large diff output.",
                        style = MaterialTheme.typography.caption,
                        color = MaterialTheme.colors.onSurface.copy(alpha = 0.65f),
                    )
                }
            }
        }
    }
}

private data class DiffFileStat(
    val path: String,
    val additions: Int,
    val deletions: Int,
)

private data class RenderDiffLine(
    val text: String,
    val color: Color,
)

private data class DiffPreview(
    val lines: List<RenderDiffLine>,
    val truncated: Boolean,
)

private const val MAX_DIFF_PREVIEW_LINES = 120
private const val MAX_DIFF_PREVIEW_CHARS = 12000

private fun buildDiffPreview(diffText: String): DiffPreview {
    val truncatedByChars = diffText.length > MAX_DIFF_PREVIEW_CHARS
    val limitedText = if (truncatedByChars) {
        diffText.take(MAX_DIFF_PREVIEW_CHARS)
    } else {
        diffText
    }
    val allLines = limitedText.lines()
    val truncatedByLines = allLines.size > MAX_DIFF_PREVIEW_LINES
    val previewLines = if (truncatedByLines) {
        allLines.take(MAX_DIFF_PREVIEW_LINES)
    } else {
        allLines
    }
    return DiffPreview(
        lines = parseDiffLines(previewLines, Color(0xFF202124)),
        truncated = truncatedByChars || truncatedByLines,
    )
}

private fun parseDiffLines(lines: List<String>, neutralColor: Color): List<RenderDiffLine> = lines.map { line ->
    when {
        line.startsWith("diff --git") || line.startsWith("--- ") || line.startsWith("+++ ") -> {
            RenderDiffLine(line, Color(0xFF1565C0))
        }
        line.startsWith("@@") -> RenderDiffLine(line, Color(0xFF6A1B9A))
        line.startsWith("+") && !line.startsWith("+++") -> RenderDiffLine(line, Color(0xFF2E7D32))
        line.startsWith("-") && !line.startsWith("---") -> RenderDiffLine(line, Color(0xFFC62828))
        else -> RenderDiffLine(line, neutralColor)
    }
}

private fun JsonObject.summaryLines(): List<String> {
    val lines = this["summary_lines"] as? JsonArray ?: return emptyList()
    return lines.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }
}

private fun JsonObject.diffFiles(): List<DiffFileStat> {
    val files = this["files"] as? JsonArray ?: return emptyList()
    return files.mapNotNull { element ->
        val file = element as? JsonObject ?: return@mapNotNull null
        DiffFileStat(
            path = (file["path"] as? JsonPrimitive)?.contentOrNull ?: return@mapNotNull null,
            additions = (file["additions"] as? JsonPrimitive)?.contentOrNull?.toIntOrNull() ?: 0,
            deletions = (file["deletions"] as? JsonPrimitive)?.contentOrNull?.toIntOrNull() ?: 0,
        )
    }
}

private val JsonPrimitive.contentOrNull: String?
    get() = content

@Preview
@Composable
private fun DiffOutputViewPreview() {
    MaterialTheme {
        Card(modifier = Modifier.fillMaxWidth(), elevation = 0.dp) {
            DiffOutputView(
                item = OutputTimelineItemState(
                    sequence = 1,
                    stepId = "fetch_bundle",
                    stepName = "Fetch PR Review Bundle",
                    format = OutputVisualFormat.DIFF,
                    title = "Files affected:",
                    content = "diff --git a/src/foo.py b/src/foo.py\n--- a/src/foo.py\n+++ b/src/foo.py\n@@ -1,2 +1,3 @@\n line\n-old\n+new\n+extra",
                    metadata = JsonObject(
                        mapOf(
                            "summary_lines" to JsonArray(listOf(JsonPrimitive("1 file changed, 2 insertions(+), 1 deletions(-)"))),
                            "files" to JsonArray(
                                listOf(
                                    JsonObject(
                                        mapOf(
                                            "path" to JsonPrimitive("src/foo.py"),
                                            "additions" to JsonPrimitive(2),
                                            "deletions" to JsonPrimitive(1),
                                        )
                                    )
                                )
                            ),
                        )
                    ),
                )
            )
        }
    }
}
