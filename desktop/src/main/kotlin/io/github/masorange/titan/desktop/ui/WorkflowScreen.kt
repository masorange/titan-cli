package io.github.masorange.titan.desktop.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.selection.SelectionContainer
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
import io.github.masorange.titan.desktop.state.ActivePromptState
import io.github.masorange.titan.desktop.state.RunVisualStatus
import io.github.masorange.titan.desktop.state.StepItemState
import io.github.masorange.titan.desktop.state.WorkflowScreenState
import kotlinx.serialization.json.JsonPrimitive
import androidx.compose.ui.unit.dp

@Composable
fun WorkflowScreen(
    screenState: WorkflowScreenState,
    projectRoot: String,
    commandPreview: String,
    protocolEvents: List<String>,
    diagnostics: List<String>,
    onStart: () -> Unit,
    onCancel: () -> Unit,
    promptDraftText: String,
    onPromptDraftTextChange: (String) -> Unit,
    isSubmittingPrompt: Boolean,
    onSubmitText: (() -> Unit)?,
    onSubmitConfirm: ((Boolean) -> Unit)?,
) {
    Row(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        horizontalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Column(
            modifier = Modifier.weight(0.38f).fillMaxHeight(),
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
                    Text("Total steps: ${screenState.header.totalSteps?.toString() ?: "unknown"}")
                    Text("Titan command: $commandPreview")
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = onStart, enabled = !screenState.isRunActive) {
                            Text("Start")
                        }
                        OutlinedButton(onClick = onCancel, enabled = screenState.isRunActive) {
                            Text("Cancel")
                        }
                    }
                }
            }

            SectionCard(title = "Step List", modifier = Modifier.weight(1f)) {
                StepListPanel(steps = screenState.steps)
            }

            SectionCard(title = "Active Prompt") {
                PromptPanel(
                    prompt = screenState.activePrompt,
                    promptDraftText = promptDraftText,
                    onPromptDraftTextChange = onPromptDraftTextChange,
                    canSubmit = canSubmitPrompt(
                        prompt = screenState.activePrompt,
                        promptDraftText = promptDraftText,
                        isSubmitting = isSubmittingPrompt,
                    ),
                    isSubmitting = isSubmittingPrompt,
                    onSubmitText = { onSubmitText?.invoke() },
                    onSubmitConfirm = { onSubmitConfirm?.invoke(it) },
                )
            }
        }

        Column(
            modifier = Modifier.weight(0.62f).fillMaxHeight(),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            SectionCard(title = "Output Timeline / Raw Event Stream", modifier = Modifier.weight(1f)) {
                TimelinePanel(state = screenState, rawEvents = protocolEvents)
            }

            SectionCard(title = "Diagnostics (stderr)", modifier = Modifier.height(220.dp)) {
                LogPanel(lines = diagnostics, emptyMessage = "No diagnostics yet.")
            }
        }
    }
}

@Composable
private fun StepListPanel(steps: List<StepItemState>) {
    if (steps.isEmpty()) {
        PlaceholderBlock("No steps visible yet. The list will be derived from V1 step events.")
        return
    }

    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        items(steps, key = { it.stepId }) { step ->
            Card(elevation = 2.dp) {
                Column(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
                    Text("[${step.stepIndex}] ${step.stepName}", style = MaterialTheme.typography.subtitle1)
                    Text("Status: ${step.status.name.lowercase()}")
                    Text("Plugin: ${step.plugin ?: "unknown"}")
                    step.message?.let { Text("Message: $it") }
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
        PlaceholderBlock("No active prompt. The prompt panel opens only on `prompt_requested`.")
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
            }
            else -> {
                PlaceholderBlock("Prompt type `${prompt.promptType}` is not supported in the V1 desktop PoC.")
            }
        }
        if (prompt.options.isNotEmpty()) {
            Text("Options:")
            prompt.options.forEach { option ->
                Text("- ${option.label}")
            }
        }
        if (prompt.promptType == "text") {
            OutlinedButton(onClick = onSubmitText, enabled = canSubmit) {
                Text(if (isSubmitting) "Submitting..." else "Submit")
            }
        }
    }
}

@Composable
private fun TimelinePanel(
    state: WorkflowScreenState,
    rawEvents: List<String>,
) {
    if (state.timeline.isEmpty()) {
        if (rawEvents.isEmpty()) {
            PlaceholderBlock("No protocol events captured yet.")
            return
        }
        LogPanel(lines = rawEvents, emptyMessage = "No protocol events captured yet.")
        return
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(state.timeline, key = { "${it.sequence}:${it.stepId}:${it.title}" }) { item ->
            Card(elevation = 2.dp) {
                Column(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
                    Text(item.title ?: item.stepName ?: item.stepId ?: "Output", style = MaterialTheme.typography.subtitle1)
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

private fun kotlinx.serialization.json.JsonElement?.renderPromptDefault(): String {
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

@Composable
private fun LogPanel(lines: List<String>, emptyMessage: String) {
    if (lines.isEmpty()) {
        PlaceholderBlock(emptyMessage)
        return
    }

    SelectionContainer {
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .background(Color(0xFF101418))
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            items(lines) { line ->
                Text(
                    text = line,
                    color = Color(0xFFE6EDF3),
                    fontFamily = FontFamily.Monospace,
                )
            }
        }
    }
}
