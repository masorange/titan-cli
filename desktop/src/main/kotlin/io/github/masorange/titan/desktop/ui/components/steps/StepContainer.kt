package io.github.masorange.titan.desktop.ui.components.steps

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import es.masorange.freyja.core.theme.typography.Body2
import io.github.masorange.titan.desktop.state.StepVisualStatus
import io.github.masorange.titan.desktop.theme.Body2RegularText
import io.github.masorange.titan.desktop.theme.Body2SecondaryText
import io.github.masorange.titan.desktop.theme.CaptionRegularText
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import io.github.masorange.titan.desktop.ui.LocalTheme
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun StepContainer(
    title: String,
    stepBadge: String? = null,
    status: StepVisualStatus? = null,
    startedAt: String? = null,
    subtitle: String? = null,
    message: String? = null,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    val colors = LocalTheme.current.colors.ui
    Card(
        modifier = modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = colors.workflowCardBorder,
                shape = RoundedCornerShape(Spacing.s4)
            ),
        elevation = 4.dp,
        shape = RoundedCornerShape(Spacing.s4)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(Spacing.s5),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(colors.workflowHeaderBackground)
                    .padding(Spacing.s6),
                horizontalArrangement = Arrangement.spacedBy(Spacing.s4),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                StatusDot(status = status)
                Text(
                    text = title,
                    style = MaterialTheme.typography.subtitle1,
                    fontWeight = FontWeight.SemiBold,
                )
                stepBadge?.let {
                    StepBadge(label = it)
                }
                Spacer(modifier = Modifier.weight(1f))
                startedAt?.let {
                    Text(
                        text = it,
                        style = MaterialTheme.typography.caption,
                        color = MaterialTheme.colors.onSurface.copy(alpha = 0.7f),
                    )
                }
            }

            if (subtitle != null || message != null) {
                Column(modifier = Modifier.padding(Spacing.s6)) {
                    subtitle?.let {
                        CaptionRegularText(
                            text = it,
                            color = MaterialTheme.colors.onSurface.copy(alpha = 0.76f),
                        )
                    }

                    message?.let {
                        Body2SecondaryText(text = it)
                    }
                }
            }

            Column(modifier = Modifier.padding(Spacing.s6)) {
                content()
            }
        }
    }
}

@Composable
private fun StatusDot(status: StepVisualStatus?) {
    val colors = LocalTheme.current.colors.ui
    val color = when (status) {
        StepVisualStatus.SUCCESS -> colors.workflowStepSuccess.accent
        StepVisualStatus.FAILED -> colors.workflowStepFailed.accent
        StepVisualStatus.SKIPPED -> colors.workflowStepSkipped.accent
        StepVisualStatus.RUNNING -> colors.workflowStepRunning.accent
        StepVisualStatus.PENDING, null -> colors.workflowNeutralDot
    }

    androidx.compose.foundation.layout.Box(
        modifier = Modifier
            .size(Spacing.s5)
            .background(color = color, shape = CircleShape),
    )
}

@Composable
private fun StepBadge(label: String) {
    Card(elevation = 0.dp) {
        Text(
            text = label,
            modifier = Modifier.padding(horizontal = Spacing.s4, vertical = Spacing.s2),
            style = MaterialTheme.typography.caption,
            fontWeight = FontWeight.Medium,
            color = MaterialTheme.colors.onSurface.copy(alpha = 0.7f),
        )
    }
}

@Preview
@Composable
private fun StepContainerPreview() {
    MaterialTheme {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color.White)
                .padding(Spacing.s6)
        ) {
            StepContainer(
                title = "Step 1",
                subtitle = "Subtitle",
                message = "This is a message",
                startedAt = "2023-01-01 12:00:00",
                status = StepVisualStatus.SUCCESS,
            ) {
                Text(text = "This is a step")
            }
        }
    }
}
