package io.github.masorange.titan.desktop.adapter

import kotlinx.coroutines.flow.Flow

interface TitanWorkflowAdapter {
    val launchConfig: TitanLaunchConfig

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
