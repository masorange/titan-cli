package io.github.masorange.titan.desktop

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.material.MaterialTheme
import io.github.masorange.titan.desktop.adapter.LocalTitanCliAdapter
import io.github.masorange.titan.desktop.adapter.RunningTitanProcess
import io.github.masorange.titan.desktop.protocol.EventStreamDecoder
import io.github.masorange.titan.desktop.protocol.PromptCommandEncoder
import io.github.masorange.titan.desktop.state.WorkflowScreenState
import io.github.masorange.titan.desktop.state.WorkflowScreenStateReducer
import io.github.masorange.titan.desktop.ui.WorkflowScreen
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonPrimitive

@Composable
fun App() {
    MaterialTheme {
        val adapter = remember { LocalTitanCliAdapter() }
        val launchConfig = remember { adapter.launchConfig }
        val scope = rememberCoroutineScope()
        val protocolEvents = remember { mutableStateListOf<String>() }
        val diagnostics = remember { mutableStateListOf<String>() }
        var screenState by remember {
            mutableStateOf(
                WorkflowScreenStateReducer.initialState(
                    projectPath = launchConfig.projectRoot.toString(),
                    workflowName = launchConfig.workflowName,
                )
            )
        }
        var promptDraftText by remember { mutableStateOf("") }
        var isSubmittingPrompt by remember { mutableStateOf(false) }
        var processHandle by remember { mutableStateOf<RunningTitanProcess?>(null) }

        fun appendLine(target: MutableList<String>, value: String) {
            target += value
            if (target.size > 200) {
                target.removeAt(0)
            }
        }

        LaunchedEffect(screenState.activePrompt?.promptId) {
            val prompt = screenState.activePrompt ?: return@LaunchedEffect
            when (prompt.promptType) {
                "text" -> {
                    promptDraftText = prompt.defaultValue.asStringOrDefault(default = "")
                }
            }
        }

        fun submitPromptValue(value: JsonPrimitive) {
            val prompt = screenState.activePrompt ?: return
            val activeProcess = processHandle ?: return
            val runId = screenState.runId ?: return
            val textPromptBlocked = prompt.promptType == "text" && prompt.required && value.content.isBlank()
            if (textPromptBlocked || isSubmittingPrompt) {
                return
            }

            isSubmittingPrompt = true
            scope.launch {
                runCatching {
                    PromptCommandEncoder.encodeSubmitPromptResponse(
                        runId = runId,
                        promptId = prompt.promptId,
                        value = value,
                    )
                }.onSuccess { commandJson ->
                    runCatching { activeProcess.sendCommand(commandJson) }
                        .onFailure { error ->
                            isSubmittingPrompt = false
                            appendLine(diagnostics, error.message ?: error.toString())
                        }
                }.onFailure { error ->
                    isSubmittingPrompt = false
                    appendLine(diagnostics, error.message ?: error.toString())
                }
            }
        }

        LaunchedEffect(processHandle) {
            val activeProcess = processHandle ?: return@LaunchedEffect
            launch {
                activeProcess.stdoutLines.collect { line ->
                    appendLine(protocolEvents, line)

                    val event = EventStreamDecoder.decodeEventLine(line)
                    if (event == null) {
                        appendLine(diagnostics, "Invalid protocol event line: $line")
                        return@collect
                    }

                    screenState = WorkflowScreenStateReducer.reduce(screenState, event)
                    if (screenState.activePrompt == null) {
                        isSubmittingPrompt = false
                    }
                }
            }
            launch {
                activeProcess.stderrLines.collect { line ->
                    appendLine(diagnostics, line)
                }
            }
            launch {
                val exitCode = activeProcess.awaitExit()
                if (!screenState.isTerminal) {
                    diagnostics += "Process finished with exit code $exitCode"
                }
                processHandle = null
            }
        }

        WorkflowScreen(
            screenState = screenState,
            projectRoot = launchConfig.projectRoot.toString(),
            commandPreview = launchConfig.command.joinToString(" "),
            protocolEvents = protocolEvents,
            diagnostics = diagnostics,
            onStart = {
                if (processHandle != null) {
                    return@WorkflowScreen
                }
                protocolEvents.clear()
                diagnostics.clear()
                promptDraftText = ""
                isSubmittingPrompt = false
                screenState = WorkflowScreenStateReducer.initialState(
                    projectPath = launchConfig.projectRoot.toString(),
                    workflowName = launchConfig.workflowName,
                )
                scope.launch {
                    runCatching { adapter.startDemoRun() }
                        .onSuccess { runningProcess ->
                            processHandle = runningProcess
                        }
                        .onFailure { error ->
                            appendLine(diagnostics, error.message ?: error.toString())
                        }
                }
            },
            onCancel = {
                val activeProcess = processHandle ?: return@WorkflowScreen
                scope.launch {
                    activeProcess.cancelRun()
                }
            },
            promptDraftText = promptDraftText,
            onPromptDraftTextChange = { promptDraftText = it },
            isSubmittingPrompt = isSubmittingPrompt,
            onSubmitText = { submitPromptValue(JsonPrimitive(promptDraftText)) },
            onSubmitConfirm = { submitPromptValue(JsonPrimitive(it)) },
        )
    }
}

private fun kotlinx.serialization.json.JsonElement?.asStringOrDefault(default: String): String {
    val primitive = this as? JsonPrimitive ?: return default
    return primitive.content
}
