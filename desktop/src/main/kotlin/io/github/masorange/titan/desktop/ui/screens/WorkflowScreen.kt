package io.github.masorange.titan.desktop.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.ActivePromptState
import io.github.masorange.titan.desktop.state.ItemReviewDecisionState
import io.github.masorange.titan.desktop.state.OutputVisualFormat
import io.github.masorange.titan.desktop.state.RunVisualStatus
import io.github.masorange.titan.desktop.state.StepItemState
import io.github.masorange.titan.desktop.state.StepVisualStatus
import io.github.masorange.titan.desktop.state.WorkflowScreenState
import io.github.masorange.titan.desktop.state.RunHeaderState
import io.github.masorange.titan.desktop.state.OutputItemState
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
    submittingInteractionId: String?,
    isLoadingWorkflow: Boolean,
    isStartingRun: Boolean,
    activeErrorMessage: String?,
    onDismissError: () -> Unit,
    onSubmitText: (() -> Unit)?,
    onSubmitConfirm: ((Boolean) -> Unit)?,
    onSelectInteractionOption: ((String, String) -> Unit)?,
    onSubmitItemReview: ((String, List<ItemReviewDecisionState>, Boolean) -> Unit)?,
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
        submittingInteractionId = submittingInteractionId,
        isLoadingWorkflow = isLoadingWorkflow,
        isStartingRun = isStartingRun,
        onSubmitText = { onSubmitText?.invoke() },
        onSubmitConfirm = { onSubmitConfirm?.invoke(it) },
        onSelectInteractionOption = { interactionId, optionId ->
            onSelectInteractionOption?.invoke(interactionId, optionId)
        },
        onSubmitItemReview = { interactionId, decisions, exitRequested ->
            onSubmitItemReview?.invoke(interactionId, decisions, exitRequested)
        },
    )
}

@Composable
fun WorkflowContent(
    screenState: WorkflowScreenState,
    onStart: () -> Unit,
    promptDraftText: String,
    onPromptDraftTextChange: (String) -> Unit,
    isSubmittingPrompt: Boolean,
    submittingInteractionId: String?,
    isLoadingWorkflow: Boolean,
    isStartingRun: Boolean,
    onSubmitText: () -> Unit,
    onSubmitConfirm: (Boolean) -> Unit,
    onSelectInteractionOption: (String, String) -> Unit,
    onSubmitItemReview: (String, List<ItemReviewDecisionState>, Boolean) -> Unit,
) {
    val themeColors = LocalTheme.current.colors
    val atmosphericBackground = Brush.radialGradient(
        colorStops = arrayOf(
            0.0f to themeColors.palette.primary.main.copy(alpha = 0.24f),
            0.45f to themeColors.palette.primary.light.copy(alpha = 0.12f),
            1.0f to Color.Transparent,
        ),
        center = Offset(280f, 260f),
        radius = 900f,
    )
    val atmosphericAccent = Brush.radialGradient(
        colorStops = arrayOf(
            0.0f to themeColors.palette.secondary.main.copy(alpha = 0.22f),
            0.5f to themeColors.palette.secondary.light.copy(alpha = 0.10f),
            1.0f to Color.Transparent,
        ),
        center = Offset(1450f, 520f),
        radius = 1050f,
    )

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(themeColors.ui.screenBackground)
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(atmosphericBackground)
        )
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(atmosphericAccent)
        )
        Column(
            modifier = Modifier
                .fillMaxSize()
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
                                submittingInteractionId = submittingInteractionId,
                                onSubmitText = onSubmitText,
                                onSubmitConfirm = onSubmitConfirm,
                                onSelectInteractionOption = onSelectInteractionOption,
                                onSubmitItemReview = onSubmitItemReview,
                            )
                        },
                    )
                }
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
                        StepVisualStatus.SUCCESS,
                        outputItems = listOf(
                            OutputItemState(
                                sequence = 1,
                                stepId = "ruff_lint",
                                stepName = "Run Ruff Linter",
                                format = OutputVisualFormat.TEXT,
                                title = "Lint summary",
                                content = "Auto-fixed 3 issue(s)",
                            )
                        )
                    ),
                    StepItemState(
                        "run_tests",
                        "Run Tests",
                        3,
                        "project",
                        StepVisualStatus.FAILED,
                        "4 test(s) failed",
                        outputItems = listOf(
                            OutputItemState(
                                sequence = 2,
                                stepId = "run_tests",
                                stepName = "Run Tests",
                                format = OutputVisualFormat.MARKDOWN,
                                title = "Pytest summary",
                                content = "## Failing tests\n\n- test_a\n- test_b",
                            )
                        )
                    ),
                    StepItemState(
                        "ai_help_tests",
                        "AI Help - Tests",
                        4,
                        "core",
                        StepVisualStatus.RUNNING,
                        activePrompt = ActivePromptState(
                            promptId = "ai-help-tests:confirm",
                            stepId = "ai_help_tests",
                            stepName = "AI Help - Tests",
                            promptType = "text",
                            message = "Describe how you want the AI to help with the failing tests.",
                            defaultValue = JsonNull,
                        )
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
                isRunActive = true,
            ),
            onStart = {},
            promptDraftText = "Focus on the failing tests only.",
            onPromptDraftTextChange = {},
            isSubmittingPrompt = false,
            submittingInteractionId = null,
            isLoadingWorkflow = false,
            isStartingRun = false,
            onSubmitText = {},
            onSubmitConfirm = {},
            onSelectInteractionOption = { _, _ -> },
            onSubmitItemReview = { _, _, _ -> },
        )
    }
}
