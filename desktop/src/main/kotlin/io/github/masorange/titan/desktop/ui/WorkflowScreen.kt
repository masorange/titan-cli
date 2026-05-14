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
import io.github.masorange.titan.desktop.state.ActivePromptState
import io.github.masorange.titan.desktop.state.RunVisualStatus
import io.github.masorange.titan.desktop.state.StepItemState
import io.github.masorange.titan.desktop.state.StepVisualStatus
import io.github.masorange.titan.desktop.state.WorkflowScreenState
import io.github.masorange.titan.desktop.state.RunHeaderState
import io.github.masorange.titan.desktop.state.OutputTimelineItemState
import io.github.masorange.titan.desktop.ui.components.WorkflowExecutionPath
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.JsonNull
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun WorkflowScreen(
    screenState: WorkflowScreenState,
    projectRoot: String,
    commandPreview: String,
    onStart: () -> Unit,
    onCancel: () -> Unit,
    promptDraftText: String,
    onPromptDraftTextChange: (String) -> Unit,
    isSubmittingPrompt: Boolean,
    isLoadingWorkflow: Boolean,
    isStartingRun: Boolean,
    isCancellingRun: Boolean,
    activeErrorMessage: String?,
    onDismissError: () -> Unit,
    onSubmitText: (() -> Unit)?,
    onSubmitConfirm: ((Boolean) -> Unit)?,
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
        projectRoot = projectRoot,
        commandPreview = commandPreview,
        onStart = onStart,
        onCancel = onCancel,
        promptDraftText = promptDraftText,
        onPromptDraftTextChange = onPromptDraftTextChange,
        isSubmittingPrompt = isSubmittingPrompt,
        isLoadingWorkflow = isLoadingWorkflow,
        isStartingRun = isStartingRun,
        isCancellingRun = isCancellingRun,
        onSubmitText = { onSubmitText?.invoke() },
        onSubmitConfirm = { onSubmitConfirm?.invoke(it) },
    )
}

@Composable
fun WorkflowContent(
    screenState: WorkflowScreenState,
    projectRoot: String,
    commandPreview: String,
    onStart: () -> Unit,
    onCancel: () -> Unit,
    promptDraftText: String,
    onPromptDraftTextChange: (String) -> Unit,
    isSubmittingPrompt: Boolean,
    isLoadingWorkflow: Boolean,
    isStartingRun: Boolean,
    isCancellingRun: Boolean,
    onSubmitText: () -> Unit,
    onSubmitConfirm: (Boolean) -> Unit,
) {

    Row(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        horizontalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Column(
            modifier = Modifier.weight(0.36f).fillMaxHeight(),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            SectionCard(title = "Run Header") {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        "Workflow: ${screenState.header.workflowTitle ?: screenState.header.workflowName ?: "Unknown"}",
                        style = MaterialTheme.typography.h6,
                    )
                    Text("Status: ${screenState.header.status.label()}")
                    Text("Project path: ${screenState.header.projectPath ?: projectRoot}")
                    Text("Run id: ${screenState.runId ?: "not started"}")
                    Text("Total steps: ${screenState.header.totalSteps?.toString() ?: screenState.steps.size.toString()}")
                    Text("Titan command: $commandPreview")
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
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
                        OutlinedButton(
                            onClick = onCancel,
                            enabled = screenState.isRunActive && !isCancellingRun
                        ) {
                            Text(if (isCancellingRun) "Cancelling..." else "Cancel")
                        }
                    }
                }
            }

            SectionCard(title = "Workflow Steps", modifier = Modifier.weight(1f)) {
                StepListPanel(steps = screenState.steps)
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
                    onSubmitText = onSubmitText,
                    onSubmitConfirm = onSubmitConfirm,
                )
            }
        }
    }
}

@Composable
private fun StepListPanel(steps: List<StepItemState>) {
    if (steps.isEmpty()) {
        PlaceholderBlock("No workflow steps available. Load workflow metadata before execution.")
        return
    }

    WorkflowExecutionPath(
        steps = steps,
        modifier = Modifier.fillMaxSize(),
    )
}

@Composable
private fun ExecutionFlowPanel(
    state: WorkflowScreenState,
    promptDraftText: String,
    onPromptDraftTextChange: (String) -> Unit,
    isSubmittingPrompt: Boolean,
    onSubmitText: () -> Unit,
    onSubmitConfirm: (Boolean) -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        RunningStepSummary(state.steps)

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
            PlaceholderBlock("No execution output yet. Output produced by running steps will appear here.")
        } else {
            TimelinePanel(state = state, modifier = Modifier.weight(1f))
        }

        state.terminalMessage?.let {
            Card(elevation = 2.dp) {
                Column(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
                    Text("Terminal State", style = MaterialTheme.typography.subtitle1)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(it)
                }
            }
        }
    }
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
        PlaceholderBlock("No active prompt.")
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
                PlaceholderBlock("Prompt type `${prompt.promptType}` is not supported in the V1 desktop PoC.")
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
                    SelectionContainer {
                        Text(item.content, fontFamily = FontFamily.Monospace)
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

private fun RunVisualStatus.label(): String = name.lowercase()

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

@Composable
private fun PlaceholderBlock(message: String) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0xFFF4F4F4))
            .padding(12.dp),
    ) {
        Text(message)
    }
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
            projectRoot = "/home/alex/git/titan-cli",
            commandPreview = "poetry run titan",
            onStart = {},
            onCancel = {},
            promptDraftText = "Focus on the failing tests only.",
            onPromptDraftTextChange = {},
            isSubmittingPrompt = false,
            isLoadingWorkflow = false,
            isStartingRun = false,
            isCancellingRun = false,
            onSubmitText = {},
            onSubmitConfirm = {},
        )
    }
}
