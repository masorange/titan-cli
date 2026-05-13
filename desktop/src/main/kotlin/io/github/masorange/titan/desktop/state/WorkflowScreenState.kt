package io.github.masorange.titan.desktop.state

import io.github.masorange.titan.desktop.protocol.PromptOption
import kotlinx.serialization.json.JsonElement

data class WorkflowScreenState(
    val runId: String? = null,
    val header: RunHeaderState,
    val steps: List<StepItemState> = emptyList(),
    val timeline: List<OutputTimelineItemState> = emptyList(),
    val activePrompt: ActivePromptState? = null,
    val terminalMessage: String? = null,
    val isRunActive: Boolean = false,
    val isTerminal: Boolean = false,
)

data class RunHeaderState(
    val workflowName: String? = null,
    val workflowTitle: String? = null,
    val projectPath: String? = null,
    val status: RunVisualStatus = RunVisualStatus.IDLE,
    val totalSteps: Int? = null,
)

data class StepItemState(
    val stepId: String,
    val stepName: String,
    val stepIndex: Int,
    val plugin: String? = null,
    val status: StepVisualStatus = StepVisualStatus.PENDING,
    val message: String? = null,
)

data class OutputTimelineItemState(
    val sequence: Int,
    val stepId: String? = null,
    val stepName: String? = null,
    val format: String,
    val title: String? = null,
    val content: String,
)

data class ActivePromptState(
    val promptId: String,
    val stepId: String? = null,
    val stepName: String? = null,
    val promptType: String,
    val message: String,
    val defaultValue: JsonElement? = null,
    val required: Boolean = true,
    val options: List<PromptOption> = emptyList(),
)

enum class RunVisualStatus {
    IDLE,
    RUNNING,
    COMPLETED,
    FAILED,
    CANCELLED,
}

enum class StepVisualStatus {
    PENDING,
    RUNNING,
    SUCCESS,
    FAILED,
    SKIPPED,
}
