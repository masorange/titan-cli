package io.github.masorange.titan.desktop.ui.components.diff

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.Card
import androidx.compose.material.MaterialTheme
import androidx.compose.material.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.DiffPresentationType
import io.github.masorange.titan.desktop.state.SemanticContentType
import io.github.masorange.titan.desktop.state.SemanticContentItemState
import io.github.masorange.titan.desktop.theme.Body2RegularText
import io.github.masorange.titan.desktop.theme.Body2StrongText
import io.github.masorange.titan.desktop.theme.CaptionRegularText
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import io.github.masorange.titan.desktop.ui.DesktopPreview
import io.github.masorange.titan.desktop.ui.LocalTheme
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun DiffOutputView(
    item: SemanticContentItemState,
    modifier: Modifier = Modifier,
) {
    val colors = LocalTheme.current.colors.ui
    val summaryLines = item.metadata.summaryLines()
    val files = item.metadata.diffFiles()
    val neutralColor = MaterialTheme.colors.onSurface.copy(alpha = 0.85f)
    val diffType = DiffPresentationType.fromWireValue(item.metadata.diffType())
    val preview = remember(item.content, colors) {
        buildDiffPreview(item.content, colors)
    }

    Column(
        modifier = modifier.fillMaxWidth().padding(Spacing.s6),
        verticalArrangement = Arrangement.spacedBy(Spacing.s4),
    ) {


        when (diffType) {
            DiffPresentationType.SUMMARY, DiffPresentationType.UNKNOWN -> {
                if (files.isNotEmpty()) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(LocalTheme.current.colors.ui.diffPreviewBackground)
                            .padding(Spacing.s4),
                        verticalArrangement = Arrangement.spacedBy(Spacing.s2),
                    ) {
                        files.forEach { file ->
                            Row(
                                horizontalArrangement = Arrangement.spacedBy(Spacing.s3),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Body2RegularText(text = file.path)
                                Body2StrongText(text = "+${file.additions}", color = colors.diffAdditions)
                                Body2StrongText(text = "-${file.deletions}", color = colors.diffDeletions)
                            }
                        }
                    }
                }

                if (summaryLines.isNotEmpty()) {
                    Column(verticalArrangement = Arrangement.spacedBy(Spacing.s2)) {
                        summaryLines.forEach { line ->
                            CaptionRegularText(text = line)
                        }
                    }
                }
            }

            DiffPresentationType.FOCUSED_HUNK,
            DiffPresentationType.FULL_PATCH -> {
                if (preview.lines.isNotEmpty()) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(colors.diffPreviewBackground, RoundedCornerShape(Spacing.s2))
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
                                color = neutralColor.copy(alpha = 0.75f),
                            )
                        }
                    }
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

private fun buildDiffPreview(
    diffText: String,
    colors: io.github.masorange.titan.desktop.theme.colors.UiColors,
): DiffPreview {
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
        lines = parseDiffLines(previewLines, colors),
        truncated = truncatedByChars || truncatedByLines,
    )
}

private fun parseDiffLines(
    lines: List<String>,
    colors: io.github.masorange.titan.desktop.theme.colors.UiColors,
): List<RenderDiffLine> = lines.map { line ->
    when {
        line.startsWith("diff --git") || line.startsWith("--- ") || line.startsWith("+++ ") -> {
            RenderDiffLine(line, colors.diffPreviewHeader)
        }

        line.startsWith("@@") -> RenderDiffLine(line, colors.diffPreviewHunk)
        line.startsWith("+") && !line.startsWith("+++") -> RenderDiffLine(line, colors.diffAdditions)
        line.startsWith("-") && !line.startsWith("---") -> RenderDiffLine(line, colors.diffDeletions)
        else -> RenderDiffLine(line, colors.diffPreviewNeutral)
    }
}

private fun JsonObject.summaryLines(): List<String> {
    val lines = this["summary_lines"] as? JsonArray ?: return emptyList()
    return lines.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }
}

private fun JsonObject.diffType(): String? = (this["type"] as? JsonPrimitive)?.contentOrNull

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
    DesktopPreview {
        Card(modifier = Modifier.fillMaxWidth(), elevation = 0.dp) {
            DiffOutputView(
                item = SemanticContentItemState(
                    sequence = 1,
                    type = SemanticContentType.DIFF,
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
