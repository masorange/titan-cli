package io.github.masorange.titan.desktop.ui.components.workflow

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.MaterialTheme
import androidx.compose.material.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.SemanticContentItemState
import io.github.masorange.titan.desktop.state.SemanticContentType
import io.github.masorange.titan.desktop.state.SemanticContentVariant
import io.github.masorange.titan.desktop.theme.Body1RegularText
import io.github.masorange.titan.desktop.theme.H2Text
import io.github.masorange.titan.desktop.theme.H3Text
import io.github.masorange.titan.desktop.theme.H4Text
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import io.github.masorange.titan.desktop.ui.DesktopPreview
import io.github.masorange.titan.desktop.ui.LocalTheme
import io.github.masorange.titan.desktop.ui.components.diff.DiffOutputView
import io.github.masorange.titan.desktop.ui.components.progress.toDisplayColor
import io.github.masorange.titan.desktop.ui.components.structuredsummary.StructuredSummaryOutputView
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun SemanticContentView(
    item: SemanticContentItemState,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.fillMaxWidth().padding(12.dp)) {
        when (item.type) {
            SemanticContentType.DIFF -> DiffOutputView(item = item)
            SemanticContentType.MARKDOWN -> MarkdownContentView(item = item)
            SemanticContentType.PROGRESS -> {
//                ProgressStatusView(
//                    message = item.content,
//                    lifecycle = item.metadata["state"]?.toString()?.trim('"') ?: "started",
//                )
            }

            SemanticContentType.STRUCTURED_SUMMARY -> StructuredSummaryOutputView(item = item)

            SemanticContentType.TEXT -> {
                Column {
                    item.title?.let {
                        H3Text(text = it, color = item.variant.toDisplayColor())
                    }
                    Body1RegularText(text = item.content, color = item.variant.toDisplayColor())
                }
            }

            SemanticContentType.TABLE,
            SemanticContentType.JSON,
            SemanticContentType.UNKNOWN -> {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(color = LocalTheme.current.colors.ui.previewBackground)
                        .padding(Spacing.s6),
                ) {
                    item.title?.let {
                        H4Text(text = it, color = item.variant.toDisplayColor())
                    }
                    Text(
                        text = item.content,
                        style = MaterialTheme.typography.body2,
                        color = item.variant.toDisplayColor(),
                        fontFamily = if (item.type == SemanticContentType.UNKNOWN) FontFamily.Monospace else null,
                    )
                }
            }
        }
    }
}

@Preview
@Composable
fun SemanticContentViewPreview() {
    DesktopPreview {
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(Spacing.s6),
        ) {
            H2Text(text = "Text")
            SemanticContentView(
                item = SemanticContentItemState(
                    sequence = 1,
                    type = SemanticContentType.TEXT,
                    title = "Lint summary",
                    content = "Auto-fixed 3 issue(s)",
                )
            )

            H2Text(text = "Progress")
            SemanticContentView(
                item = SemanticContentItemState(
                    sequence = 2,
                    type = SemanticContentType.PROGRESS,
                    content = "Fetching PR data...",
                    metadata = buildJsonObject {
                        put("state", "started")
                    },
                )
            )

            H2Text(text = "Text - Warning")
            SemanticContentView(
                item = SemanticContentItemState(
                    sequence = 3,
                    type = SemanticContentType.TEXT,
                    variant = SemanticContentVariant.WARNING,
                    title = "Warning",
                    content = "Some optional checks were skipped.",
                )
            )

            H2Text(text = "Markdown")
            SemanticContentView(
                item = SemanticContentItemState(
                    sequence = 4,
                    type = SemanticContentType.MARKDOWN,
                    title = "Review summary",
                    content = "## Findings\n\n- Guard the null path before reading `response.length`\n- Add one regression test\n\n```kotlin\nval safeResponse = response ?: return 0\n```",
                )
            )
        }
    }
}
