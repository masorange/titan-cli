package io.github.masorange.titan.desktop.protocol

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
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
    val default: JsonElement? = null,
    val required: Boolean = true,
    val options: List<PromptOption> = emptyList(),
)

@Serializable
data class PromptOption(
    val id: String,
    val label: String,
    val value: JsonElement? = null,
    val description: String? = null,
)

@Serializable
data class RunStepResult(
    val id: String,
    val title: String,
    val status: String,
    val plugin: String? = null,
    val error: String? = null,
    val outputs: List<OutputPayload> = emptyList(),
    val metadata: JsonObject = JsonObject(emptyMap()),
)

@Serializable
data class RunResult(
    @SerialName("run_id") val runId: String,
    @SerialName("workflow_name") val workflowName: String,
    val status: String,
    val steps: List<RunStepResult> = emptyList(),
    val result: OutputPayload? = null,
    val diagnostics: JsonObject = JsonObject(emptyMap()),
)

@Serializable
data class WorkflowStepSummary(
    val id: String? = null,
    val name: String? = null,
    val plugin: String? = null,
    val step: String? = null,
    val command: String? = null,
    val workflow: String? = null,
    val hook: String? = null,
)

@Serializable
data class WorkflowDetail(
    val name: String,
    val description: String? = null,
    val source: String? = null,
    val steps: List<WorkflowStepSummary> = emptyList(),
)
