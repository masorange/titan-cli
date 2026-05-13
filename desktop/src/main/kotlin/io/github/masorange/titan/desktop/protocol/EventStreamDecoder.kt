package io.github.masorange.titan.desktop.protocol

import kotlinx.serialization.json.Json

object EventStreamDecoder {
    private val json = Json { ignoreUnknownKeys = true }

    fun decodeEventLine(line: String): EngineEventEnvelope? =
        runCatching { json.decodeFromString<EngineEventEnvelope>(line) }.getOrNull()
}
