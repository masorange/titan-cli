package io.github.masorange.titan.desktop

import androidx.compose.material.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import io.github.masorange.titan.desktop.adapter.LocalTitanCliAdapter
import io.github.masorange.titan.desktop.adapter.RunningTitanProcess
import io.github.masorange.titan.desktop.protocol.EventStreamDecoder
import io.github.masorange.titan.desktop.protocol.PromptCommandEncoder
import io.github.masorange.titan.desktop.protocol.WorkflowDetail
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
        var workflowDetail by remember { mutableStateOf<WorkflowDetail?>(null) }
        var isLoadingWorkflow by remember { mutableStateOf(true) }
        var isStartingRun by remember { mutableStateOf(false) }
        var isCancellingRun by remember { mutableStateOf(false) }
        var activeErrorMessage by remember { mutableStateOf<String?>(null) }
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

        fun rebuildInitialScreenState() {
            screenState = WorkflowScreenStateReducer.initialState(
                projectPath = launchConfig.projectRoot.toString(),
                workflowName = launchConfig.workflowName,
                workflowDetail = workflowDetail,
            )
        }

        LaunchedEffect(launchConfig.workflowName, launchConfig.projectRoot.toString(), launchConfig.command.joinToString(" ")) {
            isLoadingWorkflow = true
            runCatching { adapter.describeWorkflow() }
                .onSuccess { detail ->
                    workflowDetail = detail
                    rebuildInitialScreenState()
                }
                .onFailure { error ->
                    workflowDetail = null
                    rebuildInitialScreenState()
                    activeErrorMessage = error.message ?: error.toString()
                }
            isLoadingWorkflow = false
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
                            activeErrorMessage = error.message ?: error.toString()
                            appendLine(diagnostics, error.message ?: error.toString())
                        }
                }.onFailure { error ->
                    isSubmittingPrompt = false
                    activeErrorMessage = error.message ?: error.toString()
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
                        activeErrorMessage = "Invalid protocol event line received"
                        return@collect
                    }

                    if (event.type == "run_result_emitted") {
                        val runResult = EventStreamDecoder.decodeRunResultPayload(event)
                        if (runResult == null) {
                            appendLine(diagnostics, "Invalid run_result_emitted payload")
                            activeErrorMessage = "Invalid terminal run snapshot payload"
                            return@collect
                        }
                        screenState = WorkflowScreenStateReducer.applyRunResult(screenState, runResult)
                        isSubmittingPrompt = false
                        isCancellingRun = false
                        return@collect
                    }

                    screenState = WorkflowScreenStateReducer.reduce(screenState, event)
                    if (screenState.activePrompt == null) {
                        isSubmittingPrompt = false
                    }
                    if (!screenState.isRunActive) {
                        isCancellingRun = false
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
                    activeErrorMessage = "Workflow process finished unexpectedly with exit code $exitCode"
                }
                isStartingRun = false
                isCancellingRun = false
                processHandle = null
            }
        }

        WorkflowScreen(
            screenState = screenState,
            projectRoot = launchConfig.projectRoot.toString(),
            commandPreview = launchConfig.command.joinToString(" "),
            onStart = {
                if (processHandle != null || isStartingRun || isLoadingWorkflow) {
                    return@WorkflowScreen
                }
                protocolEvents.clear()
                diagnostics.clear()
                promptDraftText = ""
                isSubmittingPrompt = false
                activeErrorMessage = null
                isStartingRun = true
                rebuildInitialScreenState()
                scope.launch {
                    runCatching { adapter.startDemoRun() }
                        .onSuccess { runningProcess ->
                            processHandle = runningProcess
                            isStartingRun = false
                        }
                        .onFailure { error ->
                            isStartingRun = false
                            activeErrorMessage = error.message ?: error.toString()
                            appendLine(diagnostics, error.message ?: error.toString())
                        }
                }
            },
            onCancel = {
                val activeProcess = processHandle ?: return@WorkflowScreen
                if (isCancellingRun) {
                    return@WorkflowScreen
                }
                isCancellingRun = true
                scope.launch {
                    runCatching { activeProcess.cancelRun() }
                        .onFailure { error ->
                            isCancellingRun = false
                            activeErrorMessage = error.message ?: error.toString()
                        }
                }
            },
            promptDraftText = promptDraftText,
            onPromptDraftTextChange = { promptDraftText = it },
            isSubmittingPrompt = isSubmittingPrompt,
            isLoadingWorkflow = isLoadingWorkflow,
            isStartingRun = isStartingRun,
            isCancellingRun = isCancellingRun,
            activeErrorMessage = activeErrorMessage,
            onDismissError = { activeErrorMessage = null },
            onSubmitText = { submitPromptValue(JsonPrimitive(promptDraftText)) },
            onSubmitConfirm = { submitPromptValue(JsonPrimitive(it)) },
        )
    }
}

private fun kotlinx.serialization.json.JsonElement?.asStringOrDefault(default: String): String {
    val primitive = this as? JsonPrimitive ?: return default
    return primitive.content
}
