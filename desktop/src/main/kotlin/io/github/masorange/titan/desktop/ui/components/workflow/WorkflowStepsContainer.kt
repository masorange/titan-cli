package io.github.masorange.titan.desktop.ui.components.workflow

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.StepItemState
import io.github.masorange.titan.desktop.state.StepVisualStatus
import io.github.masorange.titan.desktop.theme.spacings.Spacing.s6
import io.github.masorange.titan.desktop.ui.DesktopPreview
import io.github.masorange.titan.desktop.ui.LocalTheme
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun WorkflowStepsContainer(
    modifier: Modifier = Modifier,
    steps: List<StepItemState>,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(s6),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (steps.isEmpty()) {
            PlaceholderBlock()
            return
        } else {
            steps.forEach { step ->
                WorkflowExecutionPathCard(
                    modifier = Modifier.fillMaxWidth(),
                    title = step.stepName,
                    subtitle = buildSubtitle(step),
                    status = step.status,
                )
            }
        }
    }
}

@Composable
private fun PlaceholderBlock() {
    val colors = LocalTheme.current.colors.ui
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(colors.mutedSurfaceBackground)
            .padding(12.dp),
    ) {
        Text("No workflow steps available. Load workflow metadata before execution.")
    }
}

private fun buildSubtitle(step: StepItemState): String {
    val message = step.message?.takeIf { it.isNotBlank() }
    return when (step.status) {
        StepVisualStatus.SUCCESS -> message ?: "Finished"
        StepVisualStatus.RUNNING -> message ?: "Running..."
        StepVisualStatus.FAILED -> message ?: "Failed"
        StepVisualStatus.SKIPPED -> message ?: "Skipped"
        StepVisualStatus.PENDING -> message ?: "Pending"
    }
}

@Preview
@Composable
fun ComponentPreview() {
    DesktopPreview {
        WorkflowStepsContainer(
            steps = listOf(
                StepItemState(
                    "validate",
                    "Validate Input Payload",
                    1,
                    "core",
                    StepVisualStatus.SUCCESS,
                    "Finished in 0.4s"
                ),
                StepItemState(
                    "run_lint",
                    "Run Linter",
                    2,
                    "project",
                    StepVisualStatus.SUCCESS,
                    "Finished in 45s"
                ),
                StepItemState(
                    "build",
                    "Build Docker Image",
                    3,
                    "core",
                    StepVisualStatus.RUNNING,
                    "Running..."
                ),
                StepItemState(
                    "push",
                    "Push changes",
                    4,
                    "git",
                    StepVisualStatus.PENDING,
                    "Pending"
                ),
            )
        )
    }
}
