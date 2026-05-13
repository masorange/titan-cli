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
import io.github.masorange.titan.desktop.state.WorkflowScreenState
import io.github.masorange.titan.desktop.state.WorkflowScreenStateReducer
import io.github.masorange.titan.desktop.ui.WorkflowScreen
import kotlinx.coroutines.launch

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
        var processHandle by remember { mutableStateOf<RunningTitanProcess?>(null) }

        fun appendLine(target: MutableList<String>, value: String) {
            target += value
            if (target.size > 200) {
                target.removeAt(0)
            }
        }

        LaunchedEffect(processHandle) {
            val activeProcess = processHandle ?: return@LaunchedEffect
            launch {
                activeProcess.stdoutLines.collect { line ->
                    appendLine(protocolEvents, line)
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
            onSubmit = null,
        )
    }
}
