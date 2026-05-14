package io.github.masorange.titan.desktop.adapter

import io.github.masorange.titan.desktop.protocol.WorkflowDetail
import kotlinx.coroutines.flow.Flow

interface TitanWorkflowAdapter {
    val launchConfig: TitanLaunchConfig

    suspend fun describeWorkflow(): WorkflowDetail

    suspend fun startDemoRun(): RunningTitanProcess
}

interface RunningTitanProcess {
    val stdoutLines: Flow<String>
    val stderrLines: Flow<String>

    suspend fun sendCommand(commandJsonLine: String)

    suspend fun cancelRun(reason: String = "desktop_cancelled")

    suspend fun awaitExit(): Int

    fun stop()
}
