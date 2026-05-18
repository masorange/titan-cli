package io.github.masorange.titan.desktop.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
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
            .padding(s6),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
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
    WorkflowExecutionPath(
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
