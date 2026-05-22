package io.github.masorange.titan.desktop.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.AlertDialog
import androidx.compose.material.Button
import androidx.compose.material.Card
import androidx.compose.material.MaterialTheme
import androidx.compose.material.OutlinedButton
import androidx.compose.material.Text
import androidx.compose.material.TextField
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.ActiveInteractionState
import io.github.masorange.titan.desktop.state.ActivePromptState
import io.github.masorange.titan.desktop.state.RunVisualStatus
import io.github.masorange.titan.desktop.state.StepItemState
import io.github.masorange.titan.desktop.state.StepVisualStatus
import io.github.masorange.titan.desktop.state.WorkflowScreenState
import io.github.masorange.titan.desktop.state.RunHeaderState
import io.github.masorange.titan.desktop.state.OutputTimelineItemState
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import io.github.masorange.titan.desktop.ui.components.WorkflowHeader
import io.github.masorange.titan.desktop.ui.components.diff.DiffOutputView
import io.github.masorange.titan.desktop.ui.components.interactions.OptionListInteractionPanel
import io.github.masorange.titan.desktop.ui.components.steps.StepContainer
import io.github.masorange.titan.desktop.ui.components.workflowexecution.WorkflowExecutionPath
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive
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
    isCancellingRun: Boolean,
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
        isCancellingRun = isCancellingRun,
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
    isCancellingRun: Boolean,
    onSubmitText: () -> Unit,
    onSubmitConfirm: (Boolean) -> Unit,
    onSelectInteractionOption: (String) -> Unit,
) {

    Column(
        modifier = Modifier.fillMaxSize().padding(Spacing.s6)
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
            Column(
                modifier = Modifier.weight(0.36f).fillMaxHeight().padding(end = Spacing.s6),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {

                SectionCard(title = "Workflow Steps", modifier = Modifier.weight(1f)) {
                    WorkflowExecutionPath(
                        steps = screenState.steps,
                        modifier = Modifier.fillMaxSize(),
                    )
                }
            }

            Column(
                modifier = Modifier.weight(0.64f).fillMaxHeight(),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                SectionCard(title = "Execution Flow", modifier = Modifier.weight(1f)) {
                    ExecutionFlowPanel(
                        state = screenState,
                        promptDraftText = promptDraftText,
                        onPromptDraftTextChange = onPromptDraftTextChange,
                        isSubmittingPrompt = isSubmittingPrompt,
                        isSubmittingInteraction = isSubmittingInteraction,
                        onSubmitText = onSubmitText,
                        onSubmitConfirm = onSubmitConfirm,
                        onSelectInteractionOption = onSelectInteractionOption,
                    )
                }
            }
        }
    }
}

@Composable
private fun ExecutionFlowPanel(
    state: WorkflowScreenState,
    promptDraftText: String,
    onPromptDraftTextChange: (String) -> Unit,
    isSubmittingPrompt: Boolean,
    isSubmittingInteraction: Boolean,
    onSubmitText: () -> Unit,
    onSubmitConfirm: (Boolean) -> Unit,
    onSelectInteractionOption: (String) -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        RunningStepSummary(state.steps)

        state.activeInteraction?.let {
            Card(elevation = 2.dp) {
                Column(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
                    Text("Active Interaction", style = MaterialTheme.typography.subtitle1)
                    Spacer(modifier = Modifier.height(8.dp))
                    InteractionPanel(
                        steps = state.steps,
                        interaction = it,
                        isSubmitting = isSubmittingInteraction,
                        onSelectInteractionOption = onSelectInteractionOption,
                    )
                }
            }
        }

        state.activePrompt?.let {
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

        if (state.timeline.isEmpty()) {
            Text("No execution output yet. Output produced by running steps will appear here.")
        } else {
            TimelinePanel(state = state, modifier = Modifier.weight(1f))
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

@Composable
private fun InteractionPanel(
    steps: List<StepItemState>,
    interaction: ActiveInteractionState?,
    isSubmitting: Boolean,
    onSelectInteractionOption: (String) -> Unit,
) {
    if (interaction == null) {
        Text("No active interaction.")
        return
    }

    val step = interaction.stepId?.let { stepId ->
        steps.firstOrNull { it.stepId == stepId }
    }
    StepContainer(
        title = interaction.stepName ?: interaction.stepId ?: "Interaction",
        stepBadge = step?.stepIndex?.let { "STEP-${it.toString().padStart(2, '0')}" },
        status = step?.status,
        startedAt = step?.startedAtLabel,
//        subtitle = humanizeInteractionType(interaction.interactionType),
//        message = interaction.message,
    ) {
        when (interaction.interactionType) {
            "option_list" -> {
                OptionListInteractionPanel(
                    options = interaction.options,
                    isSubmitting = isSubmitting,
                    onSelect = onSelectInteractionOption,
                )
            }

            else -> {
                Text("Interaction type `${interaction.interactionType}` is not supported in the current desktop slice.")
            }
        }
    }
}

private fun humanizeInteractionType(interactionType: String): String = when (interactionType) {
    "option_list" -> "Option List"
    "review_queue" -> "Review Queue"
    "action_list" -> "Action List"
    "editable_text" -> "Editable Text"
    "batch_progress" -> "Batch Progress"
    else -> interactionType.replace('_', ' ')
}

@Composable
private fun RunningStepSummary(steps: List<StepItemState>) {
    val runningStep = steps.firstOrNull { it.status == StepVisualStatus.RUNNING }
    if (runningStep == null) {
        return
    }

    Card(elevation = 2.dp) {
        Column(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
            Text("Current Step", style = MaterialTheme.typography.subtitle1)
            Spacer(modifier = Modifier.height(4.dp))
            Text("[${runningStep.stepIndex}] ${runningStep.stepName}")
            Text("Status: running")
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

@Composable
private fun TimelinePanel(
    state: WorkflowScreenState,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(state.timeline, key = { "${it.sequence}:${it.stepId}:${it.title}" }) { item ->
            Card(elevation = 2.dp) {
                Column(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
                    Text(
                        item.title ?: item.stepName ?: item.stepId ?: "Output",
                        style = MaterialTheme.typography.subtitle1
                    )
                    Text("Format: ${item.format}")
                    Text("Step: ${item.stepName ?: item.stepId ?: "run"}")
                    Spacer(modifier = Modifier.height(4.dp))
                    if (item.format == "diff") {
                        DiffOutputView(item = item)
                    } else {
                        SelectionContainer {
                            Text(item.content, fontFamily = FontFamily.Monospace)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SectionCard(
    title: String,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Card(modifier = modifier.fillMaxWidth(), elevation = 6.dp) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(title, style = MaterialTheme.typography.h6)
            content()
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
private fun WorkflowScreenPreview() {
    MaterialTheme {
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
                        format = "text",
                        title = "Lint summary",
                        content = "Auto-fixed 3 issue(s)",
                    ),
                    OutputTimelineItemState(
                        sequence = 2,
                        stepId = "run_tests",
                        stepName = "Run Tests",
                        format = "markdown",
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
            isCancellingRun = false,
            onSubmitText = {},
            onSubmitConfirm = {},
            onSelectInteractionOption = {},
        )
    }
}
