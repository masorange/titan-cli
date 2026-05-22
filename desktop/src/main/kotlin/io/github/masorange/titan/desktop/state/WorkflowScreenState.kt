package io.github.masorange.titan.desktop.state

import io.github.masorange.titan.desktop.protocol.PromptOption
import io.github.masorange.titan.desktop.protocol.InteractionAction
import io.github.masorange.titan.desktop.protocol.WorkflowDetail
import io.github.masorange.titan.desktop.protocol.WorkflowStepSummary
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

data class WorkflowScreenState(
    val runId: String? = null,
    val header: RunHeaderState,
    val steps: List<StepItemState> = emptyList(),
    val timeline: List<OutputTimelineItemState> = emptyList(),
    val activePrompt: ActivePromptState? = null,
    val activeInteraction: ActiveInteractionState? = null,
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
    val startedAtLabel: String? = null,
)

data class OutputTimelineItemState(
    val sequence: Int,
    val stepId: String? = null,
    val stepName: String? = null,
    val format: OutputVisualFormat,
    val title: String? = null,
    val content: String,
    val metadata: JsonObject = JsonObject(emptyMap()),
)

enum class OutputVisualFormat(val wireValue: String) {
    TEXT("text"),
    MARKDOWN("markdown"),
    TABLE("table"),
    DIFF("diff"),
    STRUCTURED_SUMMARY("structured_summary"),
    WARNING("warning"),
    ERROR("error"),
    JSON("json"),
    UNKNOWN("unknown");

    companion object {
        fun fromWireValue(value: String): OutputVisualFormat = when (value) {
            TEXT.wireValue -> TEXT
            MARKDOWN.wireValue -> MARKDOWN
            TABLE.wireValue -> TABLE
            DIFF.wireValue -> DIFF
            STRUCTURED_SUMMARY.wireValue -> STRUCTURED_SUMMARY
            WARNING.wireValue -> WARNING
            ERROR.wireValue -> ERROR
            JSON.wireValue -> JSON
            else -> UNKNOWN
        }
    }
}

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

data class ActiveInteractionState(
    val interactionId: String,
    val stepId: String? = null,
    val stepName: String? = null,
    val interactionType: String,
    val message: String? = null,
    val options: List<InteractionOptionState> = emptyList(),
    val actions: List<InteractionAction> = emptyList(),
)

data class InteractionOptionState(
    val id: String,
    val label: String,
    val description: String? = null,
    val badges: List<String> = emptyList(),
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
