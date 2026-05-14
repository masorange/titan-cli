package io.github.masorange.titan.desktop.adapter

import io.github.masorange.titan.desktop.protocol.EngineCommandEnvelope
import io.github.masorange.titan.desktop.protocol.EngineEventEnvelope
import io.github.masorange.titan.desktop.protocol.WorkflowDetail
import java.io.BufferedWriter
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

class LocalTitanCliAdapter(
    resolver: TitanExecutableResolver = TitanExecutableResolver(),
) : TitanWorkflowAdapter {
    override val launchConfig: TitanLaunchConfig = resolver.resolve()
    private val json = Json { ignoreUnknownKeys = true }

    override suspend fun describeWorkflow(): WorkflowDetail = withContext(Dispatchers.IO) {
        val command = buildList {
            addAll(launchConfig.command)
            addAll(
                listOf(
                    "headless",
                    "workflows",
                    "describe",
                    launchConfig.workflowName,
                    "--project-path",
                    launchConfig.projectRoot.toString(),
                    "--json",
                )
            )
        }

        val process = ProcessBuilder(command)
            .directory(launchConfig.projectRoot.toFile())
            .redirectErrorStream(false)
            .start()

        val stdout = process.inputStream.bufferedReader().readText()
        val stderr = process.errorStream.bufferedReader().readText()
        val exitCode = process.waitFor()

        if (exitCode != 0) {
            throw IllegalStateException(
                stderr.ifBlank {
                    "Failed to describe workflow '${launchConfig.workflowName}'"
                }
            )
        }

        json.decodeFromString<WorkflowDetail>(stdout)
    }

    override suspend fun startDemoRun(): RunningTitanProcess = withContext(Dispatchers.IO) {
        val command = buildList {
            addAll(launchConfig.command)
            addAll(
                listOf(
                    "headless",
                    "runs",
                    "start",
                    launchConfig.workflowName,
                    "--project-path",
                    launchConfig.projectRoot.toString(),
                )
            )
        }

        val process = ProcessBuilder(command)
            .directory(launchConfig.projectRoot.toFile())
            .redirectErrorStream(false)
            .start()

        RunningLocalTitanProcess(process = process)
    }
}

private class RunningLocalTitanProcess(
    private val process: Process,
) : RunningTitanProcess {
    private val json = Json { ignoreUnknownKeys = true }
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val writer: BufferedWriter = process.outputStream.bufferedWriter()
    private val stdout = MutableSharedFlow<String>(extraBufferCapacity = 64)
    private val stderr = MutableSharedFlow<String>(extraBufferCapacity = 64)
    private val runId = MutableStateFlow<String?>(null)

    init {
        scope.launch {
            process.inputStream.bufferedReader().useLines { lines ->
                lines.forEach { line ->
                    stdout.emit(line)
                    captureRunId(line)
                }
            }
        }
        scope.launch {
            process.errorStream.bufferedReader().useLines { lines ->
                lines.forEach { line ->
                    stderr.emit(line)
                }
            }
        }
    }

    override val stdoutLines: Flow<String> = stdout.asSharedFlow()
    override val stderrLines: Flow<String> = stderr.asSharedFlow()

    override suspend fun sendCommand(commandJsonLine: String) {
        withContext(Dispatchers.IO) {
            writer.write(commandJsonLine)
            writer.newLine()
            writer.flush()
        }
    }

    override suspend fun cancelRun(reason: String) {
        val activeRunId = runId.asStateFlow().value
        if (activeRunId == null) {
            stop()
            return
        }

        val payload = buildJsonObject {
            put("reason", reason)
        }
        val command = EngineCommandEnvelope(
            type = "cancel_run",
            runId = activeRunId,
            payload = payload,
        )
        sendCommand(json.encodeToString(command))
    }

    override suspend fun awaitExit(): Int = withContext(Dispatchers.IO) {
        val exitCode = process.waitFor()
        scope.cancel()
        exitCode
    }

    override fun stop() {
        process.destroy()
        scope.cancel()
    }

    private fun captureRunId(line: String) {
        if (runId.value != null) {
            return
        }

        val event = runCatching { json.decodeFromString<EngineEventEnvelope>(line) }.getOrNull()
        if (event != null) {
            runId.value = event.runId
        }
    }
}
