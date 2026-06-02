package io.github.masorange.titan.desktop.ui.components.diff

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.MaterialTheme
import androidx.compose.material.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.SemanticContentItemState
import io.github.masorange.titan.desktop.state.SemanticContentType
import io.github.masorange.titan.desktop.state.SemanticContentSource
import io.github.masorange.titan.desktop.state.SemanticContentVariant
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import io.github.masorange.titan.desktop.ui.DesktopPreview
import io.github.masorange.titan.desktop.ui.LocalTheme
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.jetbrains.compose.ui.tooling.preview.Preview

private data class FocusedDiffLine(
    val lineNumber: Int?,
    val marker: String,
    val content: String,
    val role: FocusedDiffLineRole,
)

private enum class FocusedDiffLineRole {
    HEADER,
    ADDITION,
    DELETION,
    CONTEXT,
    OTHER,
}

@Composable
fun FocusedDiffView(
    item: SemanticContentItemState,
    modifier: Modifier = Modifier,
) {
    val colors = LocalTheme.current.colors.ui
    val lines = parseFocusedDiffLines(item.content)

    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(LocalTheme.current.colors.palette.grey.g200, RoundedCornerShape(Spacing.s2))
            .padding(vertical = Spacing.s3),
        verticalArrangement = Arrangement.spacedBy(1.dp),
    ) {
        lines.forEach { line ->
            val lineColor = when (line.role) {
                FocusedDiffLineRole.HEADER -> colors.diffPreviewHunk
                FocusedDiffLineRole.ADDITION -> colors.diffAdditions
                FocusedDiffLineRole.DELETION -> colors.diffDeletions
                FocusedDiffLineRole.CONTEXT -> colors.diffPreviewNeutral
                FocusedDiffLineRole.OTHER -> MaterialTheme.colors.onSurface.copy(alpha = 0.85f)
            }
            val lineNumberColor = when (line.role) {
                FocusedDiffLineRole.ADDITION -> colors.diffAdditions.copy(alpha = 0.7f)
                FocusedDiffLineRole.DELETION -> colors.diffDeletions.copy(alpha = 0.7f)
                else -> MaterialTheme.colors.onSurface.copy(alpha = 0.5f)
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = Spacing.s4, vertical = 1.dp),
                horizontalArrangement = Arrangement.spacedBy(Spacing.s3),
            ) {
                Text(
                    text = line.lineNumber?.toString() ?: "",
                    modifier = Modifier.padding(top = 1.dp),
                    style = MaterialTheme.typography.caption,
                    fontFamily = FontFamily.Monospace,
                    color = lineNumberColor,
                    textAlign = TextAlign.End,
                    maxLines = 1,
                )
                Text(
                    text = line.marker,
                    modifier = Modifier.padding(top = 1.dp),
                    style = MaterialTheme.typography.caption,
                    fontFamily = FontFamily.Monospace,
                    color = lineColor,
                    maxLines = 1,
                )
                Text(
                    text = line.content,
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.caption,
                    fontFamily = FontFamily.Monospace,
                    color = lineColor,
                )
            }
        }
    }
}

private fun parseFocusedDiffLines(diffText: String): List<FocusedDiffLine> {
    val rawLines = diffText.lines()
    if (rawLines.isEmpty()) {
        return emptyList()
    }

    val result = mutableListOf<FocusedDiffLine>()
    var currentLineNumber: Int? = null

    rawLines.forEachIndexed { index, rawLine ->
        if (index == 0 && rawLine.startsWith("@@")) {
            result += FocusedDiffLine(
                lineNumber = null,
                marker = "@@",
                content = rawLine,
                role = FocusedDiffLineRole.HEADER,
            )
            currentLineNumber = extractNewStartLine(rawLine)
            return@forEachIndexed
        }

        if (rawLine.isEmpty()) {
            result += FocusedDiffLine(
                lineNumber = currentLineNumber,
                marker = " ",
                content = "",
                role = FocusedDiffLineRole.CONTEXT,
            )
            currentLineNumber = currentLineNumber?.plus(1)
            return@forEachIndexed
        }

        val marker = rawLine.first().toString()
        val content = rawLine.drop(1)
        when {
            rawLine.startsWith("+") && !rawLine.startsWith("+++") -> {
                result += FocusedDiffLine(currentLineNumber, "+", content, FocusedDiffLineRole.ADDITION)
                currentLineNumber = currentLineNumber?.plus(1)
            }

            rawLine.startsWith("-") && !rawLine.startsWith("---") -> {
                result += FocusedDiffLine(currentLineNumber, "-", content, FocusedDiffLineRole.DELETION)
            }

            rawLine.startsWith(" ") -> {
                result += FocusedDiffLine(currentLineNumber, " ", content, FocusedDiffLineRole.CONTEXT)
                currentLineNumber = currentLineNumber?.plus(1)
            }

            else -> {
                result += FocusedDiffLine(null, marker, rawLine, FocusedDiffLineRole.OTHER)
            }
        }
    }

    return result
}

private fun extractNewStartLine(header: String): Int? {
    val match = Regex("@@ -\\d+,?\\d* \\+(\\d+),?\\d* @@").find(header) ?: return null
    return match.groupValues.getOrNull(1)?.toIntOrNull()
}

@Preview
@Composable
private fun FocusedDiffViewPreview() {
    DesktopPreview {
        FocusedDiffView(
            item = SemanticContentItemState(
                sequence = 1,
                source = SemanticContentSource.INTERACTION_CONTENT,
                type = SemanticContentType.DIFF,
                variant = SemanticContentVariant.MUTED,
                title = "Relevant diff",
                content = "@@ -24,6 +24,7 @@ fun QuantityWithCurrencyItem(\n     quantity: BigDecimal,\n     showLowQuantity: Boolean,\n     isAlertStyleNeeded: Boolean,\n-    currencySymbol = currency.symbol\n+    val quantitySymbol = currency.symbol\n+    val quantityText = formatCurrency(quantity, currency)\n \n     val quantityAnnotatedString: AnnotatedString = monetaryQuantityStyleAnnotated(",
                metadata = buildJsonObject {
                    put("type", "focused_hunk")
                    put("path", "app/src/main/kotlin/com/ragnarok/apps/ui/components/QuantityWithCurrency.kt")
                    put("line_label", "Line 32 (AI 74 via snippet)")
                    put("line", 32)
                    put("original_line", 74)
                    put("resolved_line", 32)
                    put("resolution_source", "snippet")
                },
            )
        )
    }
}
