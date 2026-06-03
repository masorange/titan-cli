package io.github.masorange.titan.desktop.ui.components.workflow

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.Button
import androidx.compose.material.Card
import androidx.compose.material.MaterialTheme
import androidx.compose.material.OutlinedButton
import androidx.compose.material.Text
import androidx.compose.material.TextField
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.ActivePromptState
import io.github.masorange.titan.desktop.state.ItemReviewDecisionState
import io.github.masorange.titan.desktop.state.RunHeaderState
import io.github.masorange.titan.desktop.state.RunVisualStatus
import io.github.masorange.titan.desktop.state.SemanticContentItemState
import io.github.masorange.titan.desktop.state.SemanticContentType
import io.github.masorange.titan.desktop.state.StepItemState
import io.github.masorange.titan.desktop.state.StepVisualStatus
import io.github.masorange.titan.desktop.state.WorkflowScreenState
import io.github.masorange.titan.desktop.theme.H3Text
import io.github.masorange.titan.desktop.ui.DesktopPreview
import io.github.masorange.titan.desktop.ui.components.progress.ProgressStatusView
import io.github.masorange.titan.desktop.ui.components.steps.StepContainer
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun ExecutionContainer(
    state: WorkflowScreenState,
    promptDraftText: String,
    onPromptDraftTextChange: (String) -> Unit,
    isSubmittingPrompt: Boolean,
    submittingInteractionId: String?,
    onSubmitText: () -> Unit,
    onSubmitConfirm: (Boolean) -> Unit,
    onSelectInteractionOption: (String, String) -> Unit,
    onSubmitItemReview: (String, List<ItemReviewDecisionState>, Boolean) -> Unit,
) {
    val listState = rememberLazyListState()
    val expandedStates = remember { mutableStateMapOf<String, Boolean>() }
    val runningStepId = state.steps.firstOrNull { it.status == StepVisualStatus.RUNNING }?.stepId
    val activeStepId = runningStepId
        ?: state.steps.firstOrNull { it.activePrompt != null }?.stepId
        ?: state.steps.firstOrNull { it.activeInteraction != null }?.stepId
    val activeStepIndex = state.steps.indexOfFirst { it.stepId == activeStepId }

    LaunchedEffect(activeStepId, activeStepIndex) {
        if (activeStepId != null && activeStepIndex >= 0) {
            listState.animateScrollToItem(activeStepIndex)
            withFrameNanos { }
            expandedStates[activeStepId] = true
        }
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        state = listState,
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        itemsIndexed(
            items = state.steps,
            key = { _, step -> step.stepId },
        ) { _, step ->
            StepContainer(
                stepId = step.stepId,
                title = step.stepName,
                stepBadge = step.stepIndex.let { "STEP-${it.toString().padStart(2, '0')}" },
                status = step.status,
                expanded = expandedStates[step.stepId] ?: false,
                onExpandedChange = { isExpanded -> expandedStates[step.stepId] = isExpanded },
                startedAt = step.startedAtLabel,
//        subtitle = humanizeInteractionType(interaction.interactionType),
//        message = interaction.message,
            ) {
                when (step.status) {
                    StepVisualStatus.PENDING -> {
                        H3Text(text = "No execution output yet. Output produced by running steps will appear here.")
                    }
                    else -> {
                        step.activeInteraction?.let {
                            InteractionPanel(
                                interaction = it,
                                isSubmitting = it.interactionId == submittingInteractionId,
                                onSelectInteractionOption = onSelectInteractionOption,
                                onSubmitItemReview = onSubmitItemReview,
                            )
                        }

                        step.activeProgress?.let {
                            ProgressStatusView(
                                modifier = Modifier.padding(12.dp),
                                message = it.message,
                                lifecycle = it.state,
                            )
                        }

                        step.activePrompt?.let {
                            Card(elevation = 2.dp) {
                                Column(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
                                    Text("Active Prompt", style = MaterialTheme.typography.subtitle1)
                                    Spacer(modifier = Modifier.height(8.dp))
                                    PromptPanel(
                                        prompt = it,
                                        promptDraftText = promptDraftText,
                                        onPromptDraftTextChange = onPromptDraftTextChange,
                                        canSubmit = canSubmitPrompt(
                                            prompt = it,
                                            promptDraftText = promptDraftText,
                                            isSubmitting = isSubmittingPrompt,
                                        ),
                                        isSubmitting = isSubmittingPrompt,
                                        onSubmitText = onSubmitText,
                                        onSubmitConfirm = onSubmitConfirm,
                                    )
                                }
                            }
                        }

                        step.contentItems.forEach { item ->
                            SemanticContentView(item = item)
                        }

                        state.terminalMessage?.let {
                            Card(elevation = 2.dp) {
                                Column(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
                                    Text("Terminal State", style = MaterialTheme.typography.subtitle1)
                                    Spacer(modifier = Modifier.height(4.dp))
                                    SelectionContainer {
                                        Text(it)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}


@Composable
private fun PromptPanel(
    prompt: ActivePromptState?,
    promptDraftText: String,
    onPromptDraftTextChange: (String) -> Unit,
    canSubmit: Boolean,
    isSubmitting: Boolean,
    onSubmitText: () -> Unit,
    onSubmitConfirm: (Boolean) -> Unit,
) {
    if (prompt == null) {
        Text("No active prompt.")
        return
    }

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Type: ${prompt.promptType}")
        Text("Prompt id: ${prompt.promptId}")
        Text("Step: ${prompt.stepName ?: prompt.stepId ?: "unknown"}")
        Text(prompt.message)
        Text("Required: ${if (prompt.required) "yes" else "no"}")
        Text("Default: ${prompt.defaultValue.renderPromptDefault()}")
        when (prompt.promptType) {
            "confirm" -> {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { onSubmitConfirm(true) }, enabled = !isSubmitting) {
                        Text(if (isSubmitting) "Submitting..." else "Confirm")
                    }
                    OutlinedButton(onClick = { onSubmitConfirm(false) }, enabled = !isSubmitting) {
                        Text("Cancel")
                    }
                }
            }

            "text" -> {
                TextField(
                    value = promptDraftText,
                    onValueChange = onPromptDraftTextChange,
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    label = { Text("Response") },
                )
                OutlinedButton(onClick = onSubmitText, enabled = canSubmit) {
                    Text(if (isSubmitting) "Submitting..." else "Submit")
                }
            }

            else -> {
                Text("Prompt type `${prompt.promptType}` is not supported in the V1 desktop PoC.")
            }
        }
    }
}

private fun canSubmitPrompt(
    prompt: ActivePromptState?,
    promptDraftText: String,
    isSubmitting: Boolean,
): Boolean {
    if (prompt == null || isSubmitting) {
        return false
    }
    return when (prompt.promptType) {
        "text" -> !prompt.required || promptDraftText.isNotBlank()
        else -> false
    }
}

private fun JsonElement?.renderPromptDefault(): String {
    val primitive = this as? JsonPrimitive ?: return "none"
    return primitive.content
}

@Preview
@Composable
fun ExecutionContainerPreview() {
    DesktopPreview {
        ExecutionContainer(
            state = WorkflowScreenState(
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
                        contentItems = listOf(
                            SemanticContentItemState(
                                sequence = 1,
                                stepId = "ruff_lint",
                                stepName = "Run Ruff Linter",
                                type = SemanticContentType.TEXT,
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
                        contentItems = listOf(
                            SemanticContentItemState(
                                sequence = 2,
                                stepId = "run_tests",
                                stepName = "Run Tests",
                                type = SemanticContentType.MARKDOWN,
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
            promptDraftText = "Focus on the failing tests only.",
            onPromptDraftTextChange = {},
            isSubmittingPrompt = false,
            submittingInteractionId = null,
            onSubmitText = {},
            onSubmitConfirm = {},
            onSelectInteractionOption = { _, _ -> },
            onSubmitItemReview = { _, _, _ -> },
        )
    }
}
