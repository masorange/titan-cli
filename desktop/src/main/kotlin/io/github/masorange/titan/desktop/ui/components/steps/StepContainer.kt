package io.github.masorange.titan.desktop.ui.components.steps

import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.Card
import androidx.compose.material.Icon
import androidx.compose.material.MaterialTheme
import androidx.compose.material.Text
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.StepVisualStatus
import io.github.masorange.titan.desktop.theme.Body2SecondaryText
import io.github.masorange.titan.desktop.theme.CaptionRegularText
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import io.github.masorange.titan.desktop.ui.DesktopPreview
import io.github.masorange.titan.desktop.ui.LocalTheme
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun StepContainer(
    modifier: Modifier = Modifier,
    stepId: String,
    title: String,
    stepBadge: String? = null,
    status: StepVisualStatus,
    expanded: Boolean? = null,
    onExpandedChange: ((Boolean) -> Unit)? = null,
    startedAt: String? = null,
    subtitle: String? = null,
    message: String? = null,
    content: @Composable () -> Unit,
) {
    var internalExpanded by remember(stepId, title) {
        mutableStateOf(status == StepVisualStatus.RUNNING)
    }
    val isExpanded = expanded ?: internalExpanded
    val setExpanded: (Boolean) -> Unit = { nextExpanded ->
        if (expanded != null) {
            onExpandedChange?.invoke(nextExpanded)
        } else {
            internalExpanded = nextExpanded
            onExpandedChange?.invoke(nextExpanded)
        }
    }

    Card(
        modifier = modifier
            .fillMaxWidth()
            .animateContentSize(),
        shape = RoundedCornerShape(Spacing.s4)
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
        ) {
            StepHeader(
                status = status,
                title = title,
                badge = stepBadge,
                startedAt = startedAt,
                isExpanded = isExpanded,
                onExpandedChange = setExpanded,
            )
            if (isExpanded) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(LocalTheme.current.colors.ui.diffPreviewBackground)
                        .padding(Spacing.s6)
                ) {
                    subtitle?.let {
                        CaptionRegularText(
                            text = it,
                            color = MaterialTheme.colors.onSurface.copy(alpha = 0.76f),
                        )
                    }
                    message?.let {
                        Body2SecondaryText(text = it)
                    }
                    content()
                }
            }
        }
    }
}

@Composable
private fun StepHeader(
    modifier: Modifier = Modifier,
    title: String,
    badge: String? = null,
    startedAt: String? = null,
    status: StepVisualStatus,
    isExpanded: Boolean,
    onExpandedChange: (Boolean) -> Unit,
) {
    val backgroundColor = when (status) {
        StepVisualStatus.PENDING -> LocalTheme.current.colors.ui.workflowHeaderBackground
        StepVisualStatus.RUNNING -> LocalTheme.current.colors.palette.primary.light
        StepVisualStatus.SUCCESS -> LocalTheme.current.colors.palette.success.light
        StepVisualStatus.FAILED -> LocalTheme.current.colors.palette.error.light
        StepVisualStatus.SKIPPED -> LocalTheme.current.colors.palette.warning.light
    }
    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(backgroundColor)
            .clickable { onExpandedChange(!isExpanded) }
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
        badge?.let {
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
        Icon(
            imageVector = if (isExpanded) {
                Icons.Filled.KeyboardArrowUp
            } else {
                Icons.Filled.KeyboardArrowDown
            },
            contentDescription = if (isExpanded) "Collapse step" else "Expand step",
            tint = MaterialTheme.colors.onSurface.copy(alpha = 0.7f),
        )
    }
}

@Composable
private fun StatusDot(status: StepVisualStatus?) {
    val colors = LocalTheme.current.colors.ui
    val color = when (status) {
        StepVisualStatus.SUCCESS -> colors.workflowStepSuccess.accent
        StepVisualStatus.FAILED -> colors.workflowStepFailed.accent
        StepVisualStatus.SKIPPED -> colors.workflowStepSkipped.accent
        StepVisualStatus.RUNNING -> LocalTheme.current.colors.palette.primary.dark
        StepVisualStatus.PENDING, null -> colors.workflowNeutralDot
    }

    Box(
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
    DesktopPreview {
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(Spacing.s5)
        ) {

            StepContainer(
                stepId = "step-1",
                title = "Step 1",
                subtitle = "Subtitle",
                message = "This is a message",
                startedAt = "2023-01-01 12:00:00",
                status = StepVisualStatus.PENDING,
            ) {
                Text(text = "This is a step")
            }

            StepContainer(
                stepId = "step-1",
                title = "Step 1",
                subtitle = "Subtitle",
                message = "This is a message",
                startedAt = "2023-01-01 12:00:00",
                status = StepVisualStatus.RUNNING,
            ) {
                Text(text = "This is a step")
            }

            StepContainer(
                stepId = "step-1",
                title = "Step 1",
                subtitle = "Subtitle",
                message = "This is a message",
                startedAt = "2023-01-01 12:00:00",
                status = StepVisualStatus.SUCCESS,
            ) {
                Text(text = "This is a step")
            }

            StepContainer(
                stepId = "step-1",
                title = "Step 1",
                subtitle = "Subtitle",
                message = "This is a message",
                startedAt = "2023-01-01 12:00:00",
                status = StepVisualStatus.FAILED,
            ) {
                Text(text = "This is a step")
            }

            StepContainer(
                stepId = "step-1",
                title = "Step 1",
                subtitle = "Subtitle",
                message = "This is a message",
                startedAt = "2023-01-01 12:00:00",
                status = StepVisualStatus.SKIPPED,
            ) {
                Text(text = "This is a step")
            }
        }
    }
}
