package io.github.masorange.titan.desktop.state

import io.github.masorange.titan.desktop.protocol.PromptOption
import io.github.masorange.titan.desktop.protocol.ContentBlock
import io.github.masorange.titan.desktop.protocol.InteractionAction
import io.github.masorange.titan.desktop.protocol.WorkflowDetail
import io.github.masorange.titan.desktop.protocol.WorkflowStepSummary
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

data class WorkflowScreenState(
    val runId: String? = null,
    val header: RunHeaderState,
    val steps: List<StepItemState> = emptyList(),
    val terminalMessage: String? = null,
    val isRunActive: Boolean = false,
    val isTerminal: Boolean = false,
    val workflowDetail: WorkflowDetail? = null,
) {
    val activePrompt: ActivePromptState?
        get() = steps.firstNotNullOfOrNull { it.activePrompt }

    val activeInteraction: ActiveInteractionState?
        get() = steps.firstNotNullOfOrNull { it.activeInteraction }

    val outputItems: List<OutputItemState>
        get() = steps.flatMap { it.outputItems }.sortedBy { it.sequence }
}

data class RunHeaderState(
    val workflowName: String,
    val workflowTitle: String,
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
    val activePrompt: ActivePromptState? = null,
    val activeInteraction: ActiveInteractionState? = null,
    val outputItems: List<OutputItemState> = emptyList(),
)

data class OutputItemState(
    val sequence: Int,
    val stepId: String? = null,
    val stepName: String? = null,
    val format: OutputVisualFormat,
    val variant: OutputVisualVariant = OutputVisualVariant.DEFAULT,
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

enum class OutputVisualVariant(val wireValue: String) {
    DEFAULT("default"),
    SUCCESS("success"),
    MUTED("muted"),
    WARNING("warning"),
    ERROR("error"),
    UNKNOWN("unknown");

    companion object {
        fun fromWireValue(value: String?): OutputVisualVariant = when (value) {
            null, DEFAULT.wireValue -> DEFAULT
            SUCCESS.wireValue -> SUCCESS
            MUTED.wireValue -> MUTED
            WARNING.wireValue -> WARNING
            ERROR.wireValue -> ERROR
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
    val interactionType: InteractionVisualType,
    val message: String? = null,
    val options: List<InteractionOptionState> = emptyList(),
    val actions: List<InteractionAction> = emptyList(),
    val itemReview: ItemReviewInteractionState? = null,
)

enum class InteractionVisualType(val wireValue: String) {
    OPTION_LIST("option_list"),
    ITEM_REVIEW("item_review"),
    ACTION_LIST("action_list"),
    EDITABLE_TEXT("editable_text"),
    BATCH_PROGRESS("batch_progress"),
    UNKNOWN("unknown");

    companion object {
        fun fromWireValue(value: String): InteractionVisualType = when (value) {
            OPTION_LIST.wireValue -> OPTION_LIST
            ITEM_REVIEW.wireValue -> ITEM_REVIEW
            ACTION_LIST.wireValue -> ACTION_LIST
            EDITABLE_TEXT.wireValue -> EDITABLE_TEXT
            BATCH_PROGRESS.wireValue -> BATCH_PROGRESS
            else -> UNKNOWN
        }
    }
}

data class InteractionOptionState(
    val id: String,
    val label: String,
    val description: String? = null,
    val badges: List<String> = emptyList(),
)

data class ItemReviewInteractionState(
    val reviewId: String,
    val items: List<ItemReviewItemState> = emptyList(),
    val initialIndex: Int = 0,
    val allowedActions: List<String> = emptyList(),
    val edit: ItemReviewEditState? = null,
    val metadata: JsonObject = JsonObject(emptyMap()),
)

data class ItemReviewItemState(
    val id: String,
    val title: String,
    val status: String? = null,
    val contentBlocks: List<ContentBlockState> = emptyList(),
    val editable: Boolean = false,
    val metadata: JsonObject = JsonObject(emptyMap()),
)

data class ItemReviewEditState(
    val enabled: Boolean,
    val label: String? = null,
    val initialValue: String? = null,
)

data class ItemReviewDecisionState(
    val itemId: String,
    val action: String,
    val content: String? = null,
)

data class ContentBlockState(
    val type: ContentBlockVisualType,
    val variant: OutputVisualVariant = OutputVisualVariant.DEFAULT,
    val title: String? = null,
    val content: String,
    val metadata: JsonObject = JsonObject(emptyMap()),
)

enum class ContentBlockVisualType(val wireValue: String) {
    TEXT("text"),
    MARKDOWN("markdown"),
    DIFF("diff"),
    STRUCTURED_SUMMARY("structured_summary"),
    UNKNOWN("unknown");

    companion object {
        fun fromWireValue(value: String): ContentBlockVisualType = when (value) {
            TEXT.wireValue -> TEXT
            MARKDOWN.wireValue -> MARKDOWN
            DIFF.wireValue -> DIFF
            STRUCTURED_SUMMARY.wireValue -> STRUCTURED_SUMMARY
            else -> UNKNOWN
        }
    }
}

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
