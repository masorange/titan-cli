package io.github.masorange.titan.desktop.protocol

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class EngineEventEnvelope(
    val type: String,
    @SerialName("run_id") val runId: String,
    val sequence: Int? = null,
    val timestamp: String? = null,
    val payload: JsonObject = JsonObject(emptyMap()),
)

@Serializable
data class EngineCommandEnvelope(
    val type: String,
    @SerialName("run_id") val runId: String,
    val timestamp: String? = null,
    val payload: JsonObject = JsonObject(emptyMap()),
)

@Serializable
data class StepRef(
    @SerialName("step_id") val stepId: String,
    @SerialName("step_name") val stepName: String,
    @SerialName("step_index") val stepIndex: Int,
)

@Serializable
data class OutputPayload(
    val format: String,
    val content: String,
    val title: String? = null,
    val metadata: JsonObject = JsonObject(emptyMap()),
)

@Serializable
data class PromptRequest(
    @SerialName("prompt_id") val promptId: String,
    @SerialName("prompt_type") val promptType: String,
    val message: String,
    val default: String? = null,
    val required: Boolean = true,
)
