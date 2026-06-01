package io.github.masorange.titan.desktop.ui.components.workflow

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.OutputItemState
import io.github.masorange.titan.desktop.state.OutputVisualFormat
import io.github.masorange.titan.desktop.state.OutputVisualVariant
import io.github.masorange.titan.desktop.theme.H2Text
import io.github.masorange.titan.desktop.theme.H3Text
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import io.github.masorange.titan.desktop.ui.DesktopPreview
import io.github.masorange.titan.desktop.ui.LocalTheme
import io.github.masorange.titan.desktop.ui.components.diff.DiffOutputView
import io.github.masorange.titan.desktop.ui.components.structuredsummary.StructuredSummaryOutputView
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun OutputContainer(
    modifier: Modifier = Modifier,
    item: OutputItemState,
) {
    Column(modifier = modifier.fillMaxWidth().padding(12.dp)) {
        when (item.format) {
            OutputVisualFormat.DIFF -> {
                DiffOutputView(item = item)
            }

            OutputVisualFormat.STRUCTURED_SUMMARY -> {
                StructuredSummaryOutputView(item = item)
            }


            OutputVisualFormat.TEXT -> {
                Column {
                    item.title?.let {
                        H3Text(text = it)
                    }
                    H3Text(text = item.content, color = item.variant.toDisplayColor())
                }
            }

            OutputVisualFormat.MARKDOWN -> {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(color = LocalTheme.current.colors.ui.previewBackground)
                        .padding(Spacing.s6),
                ) {
                    H3Text(text = item.content, color = item.variant.toDisplayColor())
                }
            }

            OutputVisualFormat.TABLE -> {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(color = LocalTheme.current.colors.ui.previewBackground)
                        .padding(Spacing.s6),
                ) {
                    H3Text(text = item.content, color = item.variant.toDisplayColor())
                }
            }
            OutputVisualFormat.WARNING -> {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(color = LocalTheme.current.colors.ui.previewBackground)
                        .padding(Spacing.s6),
                ) {
                    H3Text(text = item.content, color = item.variant.toDisplayColor())
                }
            }
            OutputVisualFormat.ERROR -> {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(color = LocalTheme.current.colors.ui.previewBackground)
                        .padding(Spacing.s6),
                ) {
                    H3Text(text = item.content, color = item.variant.toDisplayColor())
                }
            }
            OutputVisualFormat.JSON -> {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(color = LocalTheme.current.colors.ui.previewBackground)
                        .padding(Spacing.s6),
                ) {
                    H3Text(text = item.content, color = item.variant.toDisplayColor())
                }
            }
            OutputVisualFormat.UNKNOWN -> {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(color = LocalTheme.current.colors.ui.previewBackground)
                        .padding(Spacing.s6),
                ) {
                    H3Text(text = item.content, color = item.variant.toDisplayColor())
                }
            }
        }
    }
}

@Composable
private fun OutputVisualVariant.toDisplayColor(): Color = when (this) {
    OutputVisualVariant.DEFAULT,
    OutputVisualVariant.UNKNOWN -> Color.Unspecified
    OutputVisualVariant.SUCCESS -> Color(0xFF1F7A1F)
    OutputVisualVariant.MUTED -> LocalTheme.current.colors.palette.text.secondary.copy(alpha = 0.8f)
    OutputVisualVariant.WARNING -> Color(0xFF9A6700)
    OutputVisualVariant.ERROR -> Color(0xFFB42318)
}

@Preview
@Composable
fun OutputItemPreview() {
    DesktopPreview {
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(Spacing.s6)
        ) {
            Column {
                H2Text(text = "Text")
                OutputContainer(
                    item = OutputItemState(
                        sequence = 1,
                        stepId = "ruff_lint",
                        stepName = "Run Ruff Linter",
                        format = OutputVisualFormat.TEXT,
                        title = "Lint summary",
                        content = "Auto-fixed 3 issue(s)",
                    )
                )
            }

            Column {
                H2Text(text = "Markdown")
                OutputContainer(
                    item = OutputItemState(
                        sequence = 1,
                        stepId = "ruff_lint",
                        stepName = "Run Ruff Linter",
                        format = OutputVisualFormat.MARKDOWN,
                        title = "Lint summary",
                        content = "Auto-fixed 3 issue(s)",
                    )
                )
            }

            Column {
                H2Text(text = "Markdown")
                OutputContainer(
                    item = OutputItemState(
                        sequence = 1,
                        stepId = "ruff_lint",
                        stepName = "Run Ruff Linter",
                        format = OutputVisualFormat.TABLE,
                        title = "Lint summary",
                        content = "Auto-fixed 3 issue(s)",
                    )
                )
            }

            Column {
                H2Text(text = "Markdown")
                OutputContainer(
                    item = OutputItemState(
                        sequence = 1,
                        stepId = "ruff_lint",
                        stepName = "Run Ruff Linter",
                        format = OutputVisualFormat.ERROR,
                        title = "Lint summary",
                        content = "Auto-fixed 3 issue(s)",
                    )
                )
            }

            Column {
                H2Text(text = "Markdown")
                OutputContainer(
                    item = OutputItemState(
                        sequence = 1,
                        stepId = "ruff_lint",
                        stepName = "Run Ruff Linter",
                        format = OutputVisualFormat.WARNING,
                        title = "Lint summary",
                        content = "Auto-fixed 3 issue(s)",
                    )
                )
            }
            Column {
                H2Text(text = "Markdown")
                OutputContainer(
                    item = OutputItemState(
                        sequence = 1,
                        stepId = "ruff_lint",
                        stepName = "Run Ruff Linter",
                        format = OutputVisualFormat.JSON,
                        title = "Lint summary",
                        content = "Auto-fixed 3 issue(s)",
                    )
                )
            }
            Column {
                H2Text(text = "Markdown")
                OutputContainer(
                    item = OutputItemState(
                        sequence = 1,
                        stepId = "ruff_lint",
                        stepName = "Run Ruff Linter",
                        format = OutputVisualFormat.UNKNOWN,
                        title = "Lint summary",
                        content = "Auto-fixed 3 issue(s)",
                    )
                )
            }
        }
    }
}
