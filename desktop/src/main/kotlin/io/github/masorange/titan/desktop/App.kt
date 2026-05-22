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
        var isSubmittingInteraction by remember { mutableStateOf(false) }
        var processHandle by remember { mutableStateOf<RunningTitanProcess?>(null) }

        fun appendLine(target: MutableList<String>, value: String) {
            target += value
            if (target.size > 200) {
                target.removeAt(0)
            }
        }

        fun debugLog(message: String) {
            System.err.println("[desktop-debug] $message")
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

        fun submitInteractionSelection(optionId: String) {
            val interaction = screenState.activeInteraction ?: return
            val activeProcess = processHandle ?: return
            val runId = screenState.runId ?: return
            debugLog(
                "submitInteractionSelection requested interactionId=${interaction.interactionId} " +
                    "optionId=$optionId isSubmittingInteraction=$isSubmittingInteraction"
            )
            if (isSubmittingInteraction) {
                debugLog("submitInteractionSelection ignored because interaction is already submitting")
                return
            }

            isSubmittingInteraction = true
            scope.launch {
                runCatching {
                    PromptCommandEncoder.encodeSubmitInteractionResponse(
                        runId = runId,
                        interactionId = interaction.interactionId,
                        responseType = "select",
                        value = JsonPrimitive(optionId),
                    )
                }.onSuccess { commandJson ->
                    debugLog(
                        "submitInteractionSelection encoded interactionId=${interaction.interactionId} " +
                            "payloadLength=${commandJson.length}"
                    )
                    runCatching { activeProcess.sendCommand(commandJson) }
                        .onSuccess {
                            debugLog("submitInteractionSelection sendCommand completed for interactionId=${interaction.interactionId}")
                        }
                        .onFailure { error ->
                            isSubmittingInteraction = false
                            debugLog("submitInteractionSelection sendCommand failed: ${error.message ?: error}")
                            activeErrorMessage = error.message ?: error.toString()
                            appendLine(diagnostics, error.message ?: error.toString())
                        }
                }.onFailure { error ->
                    isSubmittingInteraction = false
                    debugLog("submitInteractionSelection encoding failed: ${error.message ?: error}")
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
                        debugLog("stdout invalid protocol line length=${line.length}")
                        appendLine(diagnostics, "Invalid protocol event line: $line")
                        activeErrorMessage = "Invalid protocol event line received"
                        return@collect
                    }

                    debugLog(
                        "stdout event sequence=${event.sequence} type=${event.type} " +
                            "activeInteractionBefore=${screenState.activeInteraction?.interactionId}"
                    )

                    if (event.type == "run_result_emitted") {
                        val runResult = EventStreamDecoder.decodeRunResultPayload(event)
                        if (runResult == null) {
                            debugLog("stdout run_result_emitted payload decode failed")
                            appendLine(diagnostics, "Invalid run_result_emitted payload")
                            activeErrorMessage = "Invalid terminal run snapshot payload"
                            return@collect
                        }
                        screenState = WorkflowScreenStateReducer.applyRunResult(screenState, runResult)
                        debugLog(
                            "applyRunResult status=${screenState.header.status} " +
                                "activeInteractionAfter=${screenState.activeInteraction?.interactionId}"
                        )
                        isSubmittingPrompt = false
                        isSubmittingInteraction = false
                        isCancellingRun = false
                        return@collect
                    }

                    val previousPromptId = screenState.activePrompt?.promptId
                    val previousInteractionId = screenState.activeInteraction?.interactionId
                    screenState = WorkflowScreenStateReducer.reduce(screenState, event)
                    val runningStepId = screenState.steps.firstOrNull {
                        it.status.name == "RUNNING"
                    }?.stepId
                    debugLog(
                        "state reduced sequence=${event.sequence} type=${event.type} " +
                            "activeInteractionAfter=${screenState.activeInteraction?.interactionId} " +
                            "runningStep=$runningStepId"
                    )
                    if (screenState.activePrompt == null) {
                        isSubmittingPrompt = false
                    } else if (previousPromptId != null && previousPromptId != screenState.activePrompt?.promptId) {
                        isSubmittingPrompt = false
                    }
                    if (screenState.activeInteraction == null) {
                        isSubmittingInteraction = false
                    } else if (
                        previousInteractionId != null &&
                        previousInteractionId != screenState.activeInteraction?.interactionId
                    ) {
                        isSubmittingInteraction = false
                        debugLog(
                            "interaction submit flag cleared due to interaction change " +
                                "from=$previousInteractionId to=${screenState.activeInteraction?.interactionId}"
                        )
                    }
                    if (!screenState.isRunActive) {
                        isCancellingRun = false
                    }
                }
            }
            launch {
                activeProcess.stderrLines.collect { line ->
                    debugLog("process stderr: $line")
                    appendLine(diagnostics, line)
                }
            }
            launch {
                val exitCode = activeProcess.awaitExit()
                debugLog("process exited with code=$exitCode isTerminal=${screenState.isTerminal}")
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
            onStart = {
                if (processHandle != null || isStartingRun || isLoadingWorkflow) {
                    return@WorkflowScreen
                }
                protocolEvents.clear()
                diagnostics.clear()
                promptDraftText = ""
                isSubmittingPrompt = false
                isSubmittingInteraction = false
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
            promptDraftText = promptDraftText,
            onPromptDraftTextChange = { promptDraftText = it },
            isSubmittingPrompt = isSubmittingPrompt,
            isSubmittingInteraction = isSubmittingInteraction,
            isLoadingWorkflow = isLoadingWorkflow,
            isStartingRun = isStartingRun,
            isCancellingRun = isCancellingRun,
            activeErrorMessage = activeErrorMessage,
            onDismissError = { activeErrorMessage = null },
            onSubmitText = { submitPromptValue(JsonPrimitive(promptDraftText)) },
            onSubmitConfirm = { submitPromptValue(JsonPrimitive(it)) },
            onSelectInteractionOption = ::submitInteractionSelection,
        )
    }
}

private fun kotlinx.serialization.json.JsonElement?.asStringOrDefault(default: String): String {
    val primitive = this as? JsonPrimitive ?: return default
    return primitive.content
}
