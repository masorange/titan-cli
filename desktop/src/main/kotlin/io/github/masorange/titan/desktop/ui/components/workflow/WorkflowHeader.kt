package io.github.masorange.titan.desktop.ui.components.workflow

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.Button
import androidx.compose.material.Card
import androidx.compose.material.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.RunHeaderState
import io.github.masorange.titan.desktop.state.RunVisualStatus
import io.github.masorange.titan.desktop.state.WorkflowScreenState
import io.github.masorange.titan.desktop.theme.H1Text
import io.github.masorange.titan.desktop.ui.DesktopPreview
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun WorkflowHeader(
    modifier: Modifier = Modifier,
    screenState: WorkflowScreenState,
    runHeaderState: RunHeaderState,
    onStart: () -> Unit,
    isLoadingWorkflow: Boolean,
    isStartingRun: Boolean,
) {
    Card(modifier = modifier, elevation = 6.dp) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            H1Text(text = runHeaderState.workflowTitle)
            Button(
                onClick = onStart,
                enabled = !screenState.isRunActive && !isStartingRun && !isLoadingWorkflow
            ) {
                Text(
                    when {
                        isLoadingWorkflow -> "Loading workflow..."
                        isStartingRun -> "Starting..."
                        else -> "Start"
                    }
                )
            }
        }
    }
}


@Preview
@Composable
private fun WorkflowExecutionPathCardPreview() {
    DesktopPreview {
        WorkflowHeader(
            screenState = WorkflowScreenState(
                runId = "run-preview-123",
                header = RunHeaderState(
                    workflowName = "commit-ai",
                    workflowTitle = "Commit with AI, Linter and Tests",
                    projectPath = "/home/alex/git/titan-cli",
                    status = RunVisualStatus.RUNNING,
                    totalSteps = 6,
                ),
                steps = emptyList(),
                timeline = emptyList(),
                activePrompt = null,
            ),
            runHeaderState = RunHeaderState(
                workflowName = "Example Workflow",
                workflowTitle = "Example Workflow",
            ),
            onStart = {},
            isLoadingWorkflow = false,
            isStartingRun = false,
        )
    }
}