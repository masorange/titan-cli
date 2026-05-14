package io.github.masorange.titan.desktop.state

import io.github.masorange.titan.desktop.protocol.PromptOption
import io.github.masorange.titan.desktop.protocol.WorkflowDetail
import io.github.masorange.titan.desktop.protocol.WorkflowStepSummary
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
    val workflowDetail: WorkflowDetail? = null,
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

fun WorkflowStepSummary.toPendingStepItem(index: Int): StepItemState {
    val stepId = id ?: name ?: "step_$index"
    val stepName = name ?: id ?: "Step $index"
    val pluginLabel = plugin ?: when {
        command != null -> "command"
        workflow != null -> "workflow"
        else -> null
    }
    return StepItemState(
        stepId = stepId,
        stepName = stepName,
        stepIndex = index,
        plugin = pluginLabel,
        status = StepVisualStatus.PENDING,
    )
}
