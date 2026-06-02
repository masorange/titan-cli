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

    val outputItems: List<SemanticContentItemState>
        get() = steps.flatMap { it.contentItems }.sortedBy { it.sequence }
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
    val activeProgress: ProgressItemState? = null,
    val activePrompt: ActivePromptState? = null,
    val activeInteraction: ActiveInteractionState? = null,
    val contentItems: List<SemanticContentItemState> = emptyList(),
)

data class SemanticContentItemState(
    val sequence: Int,
    val source: SemanticContentSource = SemanticContentSource.OUTPUT,
    val stepId: String? = null,
    val stepName: String? = null,
    val type: SemanticContentType,
    val variant: SemanticContentVariant = SemanticContentVariant.DEFAULT,
    val title: String? = null,
    val content: String,
    val metadata: JsonObject = JsonObject(emptyMap()),
)

enum class SemanticContentSource {
    OUTPUT,
    INTERACTION_CONTENT,
}

enum class SemanticContentType(val wireValue: String) {
    TEXT("text"),
    MARKDOWN("markdown"),
    TABLE("table"),
    DIFF("diff"),
    PROGRESS("progress"),
    STRUCTURED_SUMMARY("structured_summary"),
    JSON("json"),
    UNKNOWN("unknown");

    companion object {
        fun fromWireValue(value: String): SemanticContentType = when (value) {
            TEXT.wireValue -> TEXT
            MARKDOWN.wireValue -> MARKDOWN
            TABLE.wireValue -> TABLE
            DIFF.wireValue -> DIFF
            PROGRESS.wireValue -> PROGRESS
            STRUCTURED_SUMMARY.wireValue -> STRUCTURED_SUMMARY
            JSON.wireValue -> JSON
            else -> UNKNOWN
        }
    }
}

enum class DiffPresentationType(val wireValue: String) {
    SUMMARY("summary"),
    FOCUSED_HUNK("focused_hunk"),
    FULL_PATCH("full_patch"),
    UNKNOWN("unknown");

    companion object {
        fun fromWireValue(value: String?): DiffPresentationType = when (value) {
            SUMMARY.wireValue -> SUMMARY
            FOCUSED_HUNK.wireValue -> FOCUSED_HUNK
            FULL_PATCH.wireValue -> FULL_PATCH
            else -> UNKNOWN
        }
    }
}

data class ProgressItemState(
    val progressId: String,
    val message: String,
    val state: ProgressLifecycleState,
    val variant: SemanticContentVariant = SemanticContentVariant.DEFAULT,
    val indeterminate: Boolean = true,
)

enum class ProgressLifecycleState(val wireValue: String) {
    STARTED("started"),
    UPDATED("updated"),
    FINISHED("finished"),
    FAILED("failed"),
    UNKNOWN("unknown");

    companion object {
        fun fromWireValue(value: String?): ProgressLifecycleState = when (value) {
            STARTED.wireValue -> STARTED
            UPDATED.wireValue -> UPDATED
            FINISHED.wireValue -> FINISHED
            FAILED.wireValue -> FAILED
            else -> UNKNOWN
        }
    }
}

enum class SemanticContentVariant(val wireValue: String) {
    DEFAULT("default"),
    SUCCESS("success"),
    MUTED("muted"),
    WARNING("warning"),
    ERROR("error"),
    UNKNOWN("unknown");

    companion object {
        fun fromWireValue(value: String?): SemanticContentVariant = when (value) {
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
    val contentItems: List<SemanticContentItemState> = emptyList(),
    val editable: Boolean = false,
    val visualState: ItemReviewItemVisualState = ItemReviewItemVisualState.IDLE,
    val metadata: JsonObject = JsonObject(emptyMap()),
)

enum class ItemReviewItemVisualState {
    IDLE,
    ACTIVE,
    COMPLETED,
}

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
