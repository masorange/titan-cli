package io.github.masorange.titan.desktop.protocol

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.decodeFromJsonElement

object EventStreamDecoder {
    private val json = Json { ignoreUnknownKeys = true }

    fun decodeEventLine(line: String): EngineEventEnvelope? =
        runCatching { json.decodeFromString<EngineEventEnvelope>(line) }.getOrNull()

    fun decodeRunResultPayload(event: EngineEventEnvelope): RunResult? {
        val element = event.payload["run_result"] ?: return null
        return runCatching { json.decodeFromJsonElement<RunResult>(element) }.getOrNull()
    }
}
