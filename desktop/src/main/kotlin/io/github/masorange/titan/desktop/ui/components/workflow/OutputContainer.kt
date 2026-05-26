package io.github.masorange.titan.desktop.ui.components.workflow

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.OutputItemState
import io.github.masorange.titan.desktop.state.OutputVisualFormat
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

    fun debugLog(message: String) {
        System.err.println("[desktop-debug] $message")
    }

    Column(modifier = modifier.fillMaxWidth().padding(12.dp)) {
        debugLog("ITEM " + item.toString())
        
        when (item.format) {
            OutputVisualFormat.DIFF -> {
                DiffOutputView(item = item)
            }

            OutputVisualFormat.STRUCTURED_SUMMARY -> {
                debugLog("STRUCTURED_SUMMARY" + item.toString())
                StructuredSummaryOutputView(item = item)
            }


            OutputVisualFormat.TEXT -> {
                Column {
                    item.title?.let {
                        H3Text(text = it)
                    }
                    debugLog("TEXT" + item.toString())
                    H3Text(text = item.content)
                }
            }

            OutputVisualFormat.MARKDOWN -> {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(color = LocalTheme.current.colors.ui.previewBackground)
                        .padding(Spacing.s6),
                ) {
                    H3Text(text = item.content)
                }
            }

            OutputVisualFormat.TABLE -> {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(color = LocalTheme.current.colors.ui.previewBackground)
                        .padding(Spacing.s6),
                ) {
                    H3Text(text = item.content)
                }
            }
            OutputVisualFormat.WARNING -> {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(color = LocalTheme.current.colors.ui.previewBackground)
                        .padding(Spacing.s6),
                ) {
                    H3Text(text = item.content)
                }
            }
            OutputVisualFormat.ERROR -> {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(color = LocalTheme.current.colors.ui.previewBackground)
                        .padding(Spacing.s6),
                ) {
                    H3Text(text = item.content)
                }
            }
            OutputVisualFormat.JSON -> {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(color = LocalTheme.current.colors.ui.previewBackground)
                        .padding(Spacing.s6),
                ) {
                    H3Text(text = item.content)
                }
            }
            OutputVisualFormat.UNKNOWN -> {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(color = LocalTheme.current.colors.ui.previewBackground)
                        .padding(Spacing.s6),
                ) {
                    H3Text(text = item.content)
                }
            }
        }
    }
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
