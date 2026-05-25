package io.github.masorange.titan.desktop.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.AlertDialog
import androidx.compose.material.Button
import androidx.compose.material.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.key
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.ActivePromptState
import io.github.masorange.titan.desktop.state.OutputVisualFormat
import io.github.masorange.titan.desktop.state.RunVisualStatus
import io.github.masorange.titan.desktop.state.StepItemState
import io.github.masorange.titan.desktop.state.StepVisualStatus
import io.github.masorange.titan.desktop.state.WorkflowScreenState
import io.github.masorange.titan.desktop.state.RunHeaderState
import io.github.masorange.titan.desktop.state.OutputTimelineItemState
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import io.github.masorange.titan.desktop.ui.DesktopPreview
import io.github.masorange.titan.desktop.ui.LocalTheme
import io.github.masorange.titan.desktop.ui.components.workflow.WorkflowHeader
import io.github.masorange.titan.desktop.ui.components.workflow.ExecutionContainer
import io.github.masorange.titan.desktop.ui.components.workflow.WorkflowSectionCard
import io.github.masorange.titan.desktop.ui.components.workflow.WorkflowStepsContainer
import kotlinx.serialization.json.JsonNull
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun WorkflowScreen(
    screenState: WorkflowScreenState,
    onStart: () -> Unit,
    promptDraftText: String,
    onPromptDraftTextChange: (String) -> Unit,
    isSubmittingPrompt: Boolean,
    isSubmittingInteraction: Boolean,
    isLoadingWorkflow: Boolean,
    isStartingRun: Boolean,
    activeErrorMessage: String?,
    onDismissError: () -> Unit,
    onSubmitText: (() -> Unit)?,
    onSubmitConfirm: ((Boolean) -> Unit)?,
    onSelectInteractionOption: ((String) -> Unit)?,
) {
    if (activeErrorMessage != null) {
        AlertDialog(
            onDismissRequest = onDismissError,
            title = { Text("Workflow error") },
            text = { Text(activeErrorMessage) },
            confirmButton = {
                Button(onClick = onDismissError) {
                    Text("Close")
                }
            },
        )
    }

    WorkflowContent(
        screenState = screenState,
        onStart = onStart,
        promptDraftText = promptDraftText,
        onPromptDraftTextChange = onPromptDraftTextChange,
        isSubmittingPrompt = isSubmittingPrompt,
        isSubmittingInteraction = isSubmittingInteraction,
        isLoadingWorkflow = isLoadingWorkflow,
        isStartingRun = isStartingRun,
        onSubmitText = { onSubmitText?.invoke() },
        onSubmitConfirm = { onSubmitConfirm?.invoke(it) },
        onSelectInteractionOption = { onSelectInteractionOption?.invoke(it) },
    )
}

@Composable
fun WorkflowContent(
    screenState: WorkflowScreenState,
    onStart: () -> Unit,
    promptDraftText: String,
    onPromptDraftTextChange: (String) -> Unit,
    isSubmittingPrompt: Boolean,
    isSubmittingInteraction: Boolean,
    isLoadingWorkflow: Boolean,
    isStartingRun: Boolean,
    onSubmitText: () -> Unit,
    onSubmitConfirm: (Boolean) -> Unit,
    onSelectInteractionOption: (String) -> Unit,
) {

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(LocalTheme.current.colors.ui.screenBackground)
            .padding(Spacing.s6)
    ) {
        WorkflowHeader(
            modifier = Modifier.fillMaxWidth().padding(bottom = Spacing.s6),
            screenState = screenState,
            runHeaderState = screenState.header,
            onStart = onStart,
            isLoadingWorkflow = isLoadingWorkflow,
            isStartingRun = isStartingRun,
        )
        Row(modifier = Modifier.fillMaxWidth()) {
//            Column(
//                modifier = Modifier.weight(0.36f).fillMaxHeight().padding(end = Spacing.s6),
//                verticalArrangement = Arrangement.spacedBy(16.dp),
//            ) {
//                WorkflowSectionCard(
//                    modifier = Modifier.weight(1f),
//                    section = "Workflow Steps",
//                    content = {
//                        key(screenState.steps) {
//                            WorkflowStepsContainer(
//                                steps = screenState.steps,
//                                modifier = Modifier.fillMaxSize(),
//                            )
//                        }
//                    }
//                )
//            }

            Column(
                modifier = Modifier.weight(0.64f).fillMaxHeight(),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                WorkflowSectionCard(
                    modifier = Modifier.weight(1f),
                    section = "Execution Flow",
                    content = {
                        ExecutionContainer(
                            state = screenState,
                            promptDraftText = promptDraftText,
                            onPromptDraftTextChange = onPromptDraftTextChange,
                            isSubmittingPrompt = isSubmittingPrompt,
                            isSubmittingInteraction = isSubmittingInteraction,
                            onSubmitText = onSubmitText,
                            onSubmitConfirm = onSubmitConfirm,
                            onSelectInteractionOption = onSelectInteractionOption,
                        )
                    })
            }
        }
    }
}

@Preview
@Composable
private fun WorkflowScreenPreview() {
    DesktopPreview {
        WorkflowContent(
            screenState = WorkflowScreenState(
                runId = "run-preview-123",
                header = RunHeaderState(
                    workflowName = "commit-ai",
                    workflowTitle = "Commit with AI, Linter and Tests",
                    projectPath = "/home/alex/git/titan-cli",
                    status = RunVisualStatus.RUNNING,
                    totalSteps = 6,
                ),
                steps = listOf(
                    StepItemState(
                        "git_status",
                        "Check Git Status",
                        1,
                        "git",
                        StepVisualStatus.SUCCESS
                    ),
                    StepItemState(
                        "ruff_lint",
                        "Run Ruff Linter",
                        2,
                        "project",
                        StepVisualStatus.SUCCESS
                    ),
                    StepItemState(
                        "run_tests",
                        "Run Tests",
                        3,
                        "project",
                        StepVisualStatus.FAILED,
                        "4 test(s) failed"
                    ),
                    StepItemState(
                        "ai_help_tests",
                        "AI Help - Tests",
                        4,
                        "core",
                        StepVisualStatus.RUNNING
                    ),
                    StepItemState(
                        "create_commit",
                        "Create Commit",
                        5,
                        "git",
                        StepVisualStatus.PENDING
                    ),
                    StepItemState(
                        "push",
                        "Push changes to remote",
                        6,
                        "git",
                        StepVisualStatus.PENDING
                    ),
                ),
                timeline = listOf(
                    OutputTimelineItemState(
                        sequence = 1,
                        stepId = "ruff_lint",
                        stepName = "Run Ruff Linter",
                        format = OutputVisualFormat.TEXT,
                        title = "Lint summary",
                        content = "Auto-fixed 3 issue(s)",
                    ),
                    OutputTimelineItemState(
                        sequence = 2,
                        stepId = "run_tests",
                        stepName = "Run Tests",
                        format = OutputVisualFormat.MARKDOWN,
                        title = "Pytest summary",
                        content = "## Failing tests\n\n- test_a\n- test_b",
                    ),
                ),
                activePrompt = ActivePromptState(
                    promptId = "ai-help-tests:confirm",
                    stepId = "ai_help_tests",
                    stepName = "AI Help - Tests",
                    promptType = "text",
                    message = "Describe how you want the AI to help with the failing tests.",
                    defaultValue = JsonNull,
                ),
                isRunActive = true,
            ),
            onStart = {},
            promptDraftText = "Focus on the failing tests only.",
            onPromptDraftTextChange = {},
            isSubmittingPrompt = false,
            isSubmittingInteraction = false,
            isLoadingWorkflow = false,
            isStartingRun = false,
            onSubmitText = {},
            onSubmitConfirm = {},
            onSelectInteractionOption = {},
        )
    }
}
