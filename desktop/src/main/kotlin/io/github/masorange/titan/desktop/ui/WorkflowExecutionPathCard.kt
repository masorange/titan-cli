package io.github.masorange.titan.desktop.ui

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
import org.jetbrains.compose.ui.tooling.preview.Preview

private val SuccessBackground = Color(0xFFEAF7EF)
private val SuccessBorder = Color(0xFFC8F0D5)
private val SuccessIcon = Color(0xFF16A34A)

private val RunningBackground = Color(0xFFDCE7FF)
private val RunningBorder = Color(0xFF111827)
private val RunningIcon = Color(0xFF111827)

private val FailedBackground = Color(0xFFFDE8E8)
private val FailedBorder = Color(0xFFF5B5B5)
private val FailedIcon = Color(0xFFDC2626)

private val PendingBackground = Color(0xFFF8FAFC)
private val PendingBorder = Color(0xFFE2E8F0)
private val PendingIcon = Color(0xFF94A3B8)

private val SkippedBackground = Color(0xFFFFF7E6)
private val SkippedBorder = Color(0xFFF5D28C)
private val SkippedIcon = Color(0xFFD97706)

private val TitleColor = Color(0xFF0F172A)
private val SubtitleColor = Color(0xFF475569)

@Composable
fun WorkflowExecutionPathCard(
    title: String,
    subtitle: String,
    status: StepVisualStatus,
    modifier: Modifier = Modifier,
) {
    val palette = statusPalette(status)

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
                    color = TitleColor,
                    style = MaterialTheme.typography.h6.copy(fontWeight = FontWeight.Bold),
                )
                Text(
                    text = subtitle,
                    color = SubtitleColor,
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

private fun statusPalette(status: StepVisualStatus): StepVisualPalette = when (status) {
    StepVisualStatus.SUCCESS -> StepVisualPalette(
        background = SuccessBackground,
        border = SuccessBorder,
        icon = SuccessIcon,
        symbol = "✓",
    )
    StepVisualStatus.RUNNING -> StepVisualPalette(
        background = RunningBackground,
        border = RunningBorder,
        icon = RunningIcon,
        symbol = "↻",
    )
    StepVisualStatus.FAILED -> StepVisualPalette(
        background = FailedBackground,
        border = FailedBorder,
        icon = FailedIcon,
        symbol = "!",
    )
    StepVisualStatus.SKIPPED -> StepVisualPalette(
        background = SkippedBackground,
        border = SkippedBorder,
        icon = SkippedIcon,
        symbol = "-",
    )
    StepVisualStatus.PENDING -> StepVisualPalette(
        background = PendingBackground,
        border = PendingBorder,
        icon = PendingIcon,
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
