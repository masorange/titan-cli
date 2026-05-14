package io.github.masorange.titan.desktop.protocol

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

object PromptCommandEncoder {
    private val json = Json { ignoreUnknownKeys = true }

    fun encodeSubmitPromptResponse(
        runId: String,
        promptId: String,
        value: JsonElement,
    ): String {
        val payload = buildJsonObject {
            put("prompt_id", promptId)
            put("value", value)
        }
        return json.encodeToString(
            EngineCommandEnvelope(
                type = "submit_prompt_response",
                runId = runId,
                payload = payload,
            )
        )
    }
}
