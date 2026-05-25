package io.github.masorange.titan.desktop.ui.components.workflow

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.Card
import androidx.compose.material.MaterialTheme
import androidx.compose.material.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.StepVisualStatus
import io.github.masorange.titan.desktop.theme.colors.UiColors
import io.github.masorange.titan.desktop.ui.LocalTheme
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun WorkflowExecutionPathCard(
    title: String,
    subtitle: String,
    status: StepVisualStatus,
    modifier: Modifier = Modifier,
) {
    val colors = LocalTheme.current.colors.ui
    val palette = statusPalette(status, colors)

    Card(
        modifier = modifier
            .fillMaxWidth()
            .border(
                width = if (status == StepVisualStatus.RUNNING) 2.dp else 1.dp,
                color = palette.border,
                shape = RoundedCornerShape(16.dp),
            ),
        shape = RoundedCornerShape(16.dp),
        elevation = 0.dp,
        backgroundColor = palette.background,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp, vertical = 18.dp),
            horizontalArrangement = Arrangement.spacedBy(18.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .background(color = palette.icon, shape = CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = palette.symbol,
                    color = Color.White,
                    style = MaterialTheme.typography.body1.copy(fontWeight = FontWeight.Bold),
                )
            }

            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(
                    text = title,
                    color = colors.workflowTitle,
                    style = MaterialTheme.typography.h6.copy(fontWeight = FontWeight.Bold),
                )
                Text(
                    text = subtitle,
                    color = colors.workflowSubtitle,
                    style = MaterialTheme.typography.body1,
                )
            }
        }
    }
}

private data class StepVisualPalette(
    val background: Color,
    val border: Color,
    val icon: Color,
    val symbol: String,
)

private fun statusPalette(status: StepVisualStatus, colors: UiColors): StepVisualPalette = when (status) {
    StepVisualStatus.SUCCESS -> StepVisualPalette(
        background = colors.workflowStepSuccess.background,
        border = colors.workflowStepSuccess.border,
        icon = colors.workflowStepSuccess.accent,
        symbol = "✓",
    )
    StepVisualStatus.RUNNING -> StepVisualPalette(
        background = colors.workflowStepRunning.background,
        border = colors.workflowStepRunning.border,
        icon = colors.workflowStepRunning.accent,
        symbol = "↻",
    )
    StepVisualStatus.FAILED -> StepVisualPalette(
        background = colors.workflowStepFailed.background,
        border = colors.workflowStepFailed.border,
        icon = colors.workflowStepFailed.accent,
        symbol = "!",
    )
    StepVisualStatus.SKIPPED -> StepVisualPalette(
        background = colors.workflowStepSkipped.background,
        border = colors.workflowStepSkipped.border,
        icon = colors.workflowStepSkipped.accent,
        symbol = "-",
    )
    StepVisualStatus.PENDING -> StepVisualPalette(
        background = colors.workflowStepPending.background,
        border = colors.workflowStepPending.border,
        icon = colors.workflowStepPending.accent,
        symbol = "·",
    )
}

@Preview
@Composable
private fun WorkflowExecutionPathCardPreview() {
    MaterialTheme {
        Column(
            modifier = Modifier
                .background(Color.White)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            WorkflowExecutionPathCard(
                title = "Check Git Status",
                subtitle = "Finished in 2s",
                status = StepVisualStatus.SUCCESS,
            )
            WorkflowExecutionPathCard(
                title = "Build Docker Image",
                subtitle = "Running...",
                status = StepVisualStatus.RUNNING,
            )
            WorkflowExecutionPathCard(
                title = "Run Linter Skipped",
                subtitle = "Finished in 45s",
                status = StepVisualStatus.SKIPPED,
            )
            WorkflowExecutionPathCard(
                title = "Run Linter Skipped",
                subtitle = "Finished in 45s",
                status = StepVisualStatus.FAILED,
            )
            WorkflowExecutionPathCard(
                title = "Run Linter Skipped",
                subtitle = "Finished in 45s",
                status = StepVisualStatus.PENDING,
            )
        }
    }
}
