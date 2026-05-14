package io.github.masorange.titan.desktop.ui.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import io.github.masorange.titan.desktop.state.StepItemState
import io.github.masorange.titan.desktop.state.StepVisualStatus
import io.github.masorange.titan.desktop.ui.WorkflowExecutionPathCard
import io.github.masorange.titan.desktop.theme.spacings.Spacing.s6
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun WorkflowExecutionPath(
    steps: List<StepItemState>,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(s6)
    ) {
        steps.forEachIndexed { index, step ->
            WorkflowExecutionPathCard(
                title = step.stepName,
                subtitle = buildSubtitle(step),
                modifier = Modifier.fillMaxWidth(),
                isLast = index == steps.lastIndex,
                indicatorText = indicatorText(step),
                indicatorColor = indicatorColor(step),
            )
        }
    }
}

private fun buildSubtitle(step: StepItemState): String {
    val status = step.status.name.lowercase()
    val plugin = step.plugin ?: "unknown"
    val message = step.message?.takeIf { it.isNotBlank() }
    return if (message != null) {
        "$status via $plugin. $message"
    } else {
        "$status via $plugin."
    }
}

private fun indicatorText(step: StepItemState): String = when (step.status) {
    StepVisualStatus.SUCCESS -> "✓"
    StepVisualStatus.FAILED -> "!"
    StepVisualStatus.RUNNING -> "•"
    StepVisualStatus.SKIPPED -> "-"
    StepVisualStatus.PENDING -> step.stepIndex.toString()
}

private fun indicatorColor(step: StepItemState): Color = when (step.status) {
    StepVisualStatus.SUCCESS -> Color(0xFF10B981)
    StepVisualStatus.FAILED -> Color(0xFFEF4444)
    StepVisualStatus.RUNNING -> Color(0xFF2563EB)
    StepVisualStatus.SKIPPED -> Color(0xFFF59E0B)
    StepVisualStatus.PENDING -> Color(0xFF9CA3AF)
}


@Preview
@Composable
fun ComponentPreview() {
    WorkflowExecutionPath(
        steps = listOf(
            StepItemState(
                "validate",
                "Validate Input Payload",
                1,
                "core",
                StepVisualStatus.SUCCESS,
                "Schema validation successful for user_v2 object."
            ),
            StepItemState("failed", "Persist Event", 3, "core", StepVisualStatus.FAILED),
            StepItemState("transform", "Transform Input", 2, "core", StepVisualStatus.RUNNING),
            StepItemState("persist", "Persist Event", 3, "core", StepVisualStatus.PENDING),
            StepItemState("skipped", "Skipped Event", 3, "core", StepVisualStatus.SKIPPED),
        )
    )
}
