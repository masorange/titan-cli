package io.github.masorange.titan.desktop.state

import io.github.masorange.titan.desktop.protocol.EngineEventEnvelope
import io.github.masorange.titan.desktop.protocol.ContentBlock
import io.github.masorange.titan.desktop.protocol.InteractionOption
import io.github.masorange.titan.desktop.protocol.InteractionRequest
import io.github.masorange.titan.desktop.protocol.ItemReviewState
import io.github.masorange.titan.desktop.protocol.OutputPayload
import io.github.masorange.titan.desktop.protocol.PromptOption
import io.github.masorange.titan.desktop.protocol.PromptRequest
import io.github.masorange.titan.desktop.protocol.RunResult
import io.github.masorange.titan.desktop.protocol.StepRef
import io.github.masorange.titan.desktop.protocol.WorkflowDetail
import java.time.LocalTime
import java.time.format.DateTimeFormatter
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonPrimitive

object WorkflowScreenStateReducer {
    private val json = Json { ignoreUnknownKeys = true }
    private val stepStartTimeFormatter = DateTimeFormatter.ofPattern("hh:mm:ss a")

    fun initialState(
        projectPath: String,
        workflowName: String,
        workflowDetail: WorkflowDetail? = null,
    ): WorkflowScreenState = WorkflowScreenState(
        header = RunHeaderState(
            workflowName = workflowDetail?.name ?: workflowName,
            workflowTitle = workflowDetail?.description ?: "",
            projectPath = projectPath,
            totalSteps = workflowDetail?.steps?.size,
        ),
        steps = workflowDetail?.steps?.mapIndexed { index, step ->
            step.toPendingStepItem(index + 1)
        } ?: emptyList(),
        workflowDetail = workflowDetail,
    )

    fun reduce(
        state: WorkflowScreenState,
        event: EngineEventEnvelope,
    ): WorkflowScreenState = when (event.type) {
        "run_started" -> reduceRunStarted(state, event)
        "step_started" -> reduceStepStarted(state, event)
        "step_finished" -> reduceStepFinished(state, event)
        "step_failed" -> reduceStepFailed(state, event)
        "step_skipped" -> reduceStepSkipped(state, event)
        "output_emitted" -> reduceOutputEmitted(state, event)
        "prompt_requested" -> reducePromptRequested(state, event)
        "interaction_requested" -> reduceInteractionRequested(state, event)
        "run_completed" -> reduceTerminalState(state, event, RunVisualStatus.COMPLETED)
        "run_failed" -> reduceTerminalState(state, event, RunVisualStatus.FAILED)
        "run_cancelled" -> reduceTerminalState(state, event, RunVisualStatus.CANCELLED)
        else -> state
    }

    fun applyRunResult(
        state: WorkflowScreenState,
        runResult: RunResult,
    ): WorkflowScreenState {
        val runStatus = when (runResult.status) {
            "completed" -> RunVisualStatus.COMPLETED
            "failed" -> RunVisualStatus.FAILED
            "cancelled" -> RunVisualStatus.CANCELLED
            else -> state.header.status
        }
        val stepItems = runResult.steps
            .mapIndexed { index, step ->
                StepItemState(
                    stepId = step.id,
                    stepName = step.title,
                    stepIndex = index + 1,
                    plugin = step.plugin,
                    status = when (step.status) {
                        "success" -> StepVisualStatus.SUCCESS
                        "failed" -> StepVisualStatus.FAILED
                        "skipped" -> StepVisualStatus.SKIPPED
                        else -> StepVisualStatus.PENDING
                    },
                    message = step.error,
                )
            }
            .sortedBy { it.stepIndex }
        return state.copy(
            runId = runResult.runId,
            header = state.header.copy(
                workflowName = runResult.workflowName,
                status = runStatus,
                totalSteps = runResult.steps.size,
            ),
            steps = stepItems.mapIndexed { index, stepItem ->
                stepItem.copy(
                    contentItems = runResult.steps
                        .getOrNull(index)
                        ?.outputs
                        ?.mapIndexedNotNull { outputIndex, output ->
                            toSemanticOutputItem(
                                sequence = outputIndex + 1,
                                stepId = stepItem.stepId,
                                stepName = stepItem.stepName,
                                output = output,
                            )
                        }
                        ?: emptyList()
                )
            },
            terminalMessage = runResult.diagnostics["result_message"]?.asStringOrNull(),
            isRunActive = false,
            isTerminal = true,
        )
    }

    private fun reduceRunStarted(
        state: WorkflowScreenState,
        event: EngineEventEnvelope,
    ): WorkflowScreenState = state.copy(
        runId = event.runId,
        header = state.header.copy(
            workflowName = event.payload["workflow_name"]?.asStringOrNull() ?: state.header.workflowName,
            workflowTitle = event.payload["workflow_title"]?.asStringOrNull() ?: "", //TODO Change this
            projectPath = event.payload["project_path"]?.asStringOrNull() ?: state.header.projectPath,
            totalSteps = event.payload["total_steps"]?.asIntOrNull(),
            status = RunVisualStatus.RUNNING,
        ),
        terminalMessage = null,
        isRunActive = true,
        isTerminal = false,
    )

    private fun reduceStepStarted(
        state: WorkflowScreenState,
        event: EngineEventEnvelope,
    ): WorkflowScreenState {
        val step = event.payload.decodeStepRef() ?: return state
        return state.copy(
            steps = state.steps.upsertStep(step) {
                copy(
                    plugin = event.payload["plugin"]?.asStringOrNull(),
                    status = StepVisualStatus.RUNNING,
                    message = null,
                    startedAtLabel = startedAtLabel ?: currentStepStartLabel(),
                    activePrompt = null,
                    activeInteraction = null,
                )
            },
            isRunActive = true,
        )
    }

    private fun reduceStepFinished(
        state: WorkflowScreenState,
        event: EngineEventEnvelope,
    ): WorkflowScreenState {
        val step = event.payload.decodeStepRef() ?: return state
        return state.copy(
            steps = state.steps.upsertStep(step) {
                copy(
                    status = StepVisualStatus.SUCCESS,
                    message = event.payload["message"]?.asStringOrNull(),
                    activePrompt = null,
                    activeInteraction = null,
                )
            },
        )
    }

    private fun reduceStepFailed(
        state: WorkflowScreenState,
        event: EngineEventEnvelope,
    ): WorkflowScreenState {
        val step = event.payload.decodeStepRef() ?: return state
        return state.copy(
            steps = state.steps.upsertStep(step) {
                copy(
                    status = StepVisualStatus.FAILED,
                    message = event.payload["message"]?.asStringOrNull(),
                    activePrompt = null,
                    activeInteraction = null,
                )
            },
        )
    }

    private fun reduceStepSkipped(
        state: WorkflowScreenState,
        event: EngineEventEnvelope,
    ): WorkflowScreenState {
        val step = event.payload.decodeStepRef() ?: return state
        return state.copy(
            steps = state.steps.upsertStep(step) {
                copy(
                    status = StepVisualStatus.SKIPPED,
                    message = event.payload["message"]?.asStringOrNull(),
                    activePrompt = null,
                    activeInteraction = null,
                )
            },
        )
    }

    private fun reduceOutputEmitted(
        state: WorkflowScreenState,
        event: EngineEventEnvelope,
    ): WorkflowScreenState {
        val output = event.payload.decodeOutputPayload() ?: return state
        val step = event.payload.decodeStepRef()
        val format = normalizedOutputFormat(output.format)
        val variant = SemanticContentVariant.fromWireValue(
            output.metadata["variant"]?.asStringOrNull()
        )
        val progressState = if (format == SemanticContentType.PROGRESS) {
            decodeProgressItemState(output, variant)
        } else {
            null
        }
        return state.copy(
            steps = step?.let { stepRef ->
                state.steps.upsertStep(stepRef) {
                    copy(
                        status = if (status == StepVisualStatus.PENDING) StepVisualStatus.RUNNING else status,
                        startedAtLabel = startedAtLabel ?: currentStepStartLabel(),
                        activeProgress = when (progressState?.state) {
                            ProgressLifecycleState.STARTED,
                            ProgressLifecycleState.UPDATED -> progressState
                            ProgressLifecycleState.FINISHED,
                            ProgressLifecycleState.FAILED -> {
                                if (activeProgress?.progressId == progressState.progressId) null else activeProgress
                            }

                            else -> activeProgress
                        },
                        contentItems = if (format == SemanticContentType.PROGRESS) {
                            contentItems
                        } else {
                            contentItems + listOfNotNull(
                                toSemanticOutputItem(
                                    sequence = event.sequence ?: contentItems.size + 1,
                                    stepId = stepRef.stepId,
                                    stepName = stepRef.stepName,
                                    output = output,
                                )
                            )
                        },
                    )
                }
            } ?: state.steps,
        )
    }

    private fun reducePromptRequested(
        state: WorkflowScreenState,
        event: EngineEventEnvelope,
    ): WorkflowScreenState {
        val prompt = event.payload.decodePromptRequest() ?: return state
        val step = event.payload.decodeStepRef()
        return state.copy(
            steps = step?.let { stepRef ->
                state.steps.upsertStep(stepRef) {
                    copy(
                        status = if (status == StepVisualStatus.PENDING) StepVisualStatus.RUNNING else status,
                        startedAtLabel = startedAtLabel ?: currentStepStartLabel(),
                        activePrompt = ActivePromptState(
                            promptId = prompt.promptId,
                            stepId = stepRef.stepId,
                            stepName = stepRef.stepName,
                            promptType = prompt.promptType,
                            message = prompt.message,
                            defaultValue = prompt.default,
                            required = prompt.required,
                            options = prompt.options,
                        ),
                        activeInteraction = null,
                    )
                }
            } ?: state.steps,
            isRunActive = true,
        )
    }

    private fun reduceInteractionRequested(
        state: WorkflowScreenState,
        event: EngineEventEnvelope,
    ): WorkflowScreenState {
        val interaction = event.payload.decodeInteractionRequest() ?: return state
        val step = event.payload.decodeStepRef()
        val options = interaction.state["options"]?.let(::decodeInteractionOptions) ?: emptyList()
        val itemReview = if (interaction.interactionType == "item_review") {
            decodeItemReviewState(interaction.state)
        } else {
            null
        }
        return state.copy(
            steps = step?.let { stepRef ->
                state.steps.upsertStep(stepRef) {
                    copy(
                        status = if (status == StepVisualStatus.PENDING) StepVisualStatus.RUNNING else status,
                        startedAtLabel = startedAtLabel ?: currentStepStartLabel(),
                        activeInteraction = ActiveInteractionState(
                            interactionId = interaction.interactionId,
                            stepId = stepRef.stepId,
                            stepName = stepRef.stepName,
                            interactionType = InteractionVisualType.fromWireValue(interaction.interactionType),
                            message = interaction.message,
                            options = options,
                            actions = interaction.actions,
                            itemReview = itemReview,
                        ),
                        activePrompt = null,
                    )
                }
            } ?: state.steps,
            isRunActive = true,
        )
    }

    private fun reduceTerminalState(
        state: WorkflowScreenState,
        event: EngineEventEnvelope,
        status: RunVisualStatus,
    ): WorkflowScreenState = state.copy(
        header = state.header.copy(status = status),
        steps = state.steps.map { it.copy(activePrompt = null, activeInteraction = null) },
        terminalMessage = event.payload["message"]?.asStringOrNull(),
        isRunActive = false,
        isTerminal = true,
    )

    private fun List<StepItemState>.upsertStep(
        step: StepRef,
        update: StepItemState.() -> StepItemState,
    ): List<StepItemState> {
        val existingIndex = indexOfFirst { it.stepId == step.stepId }
        val current = if (existingIndex >= 0) {
            this[existingIndex]
        } else {
            StepItemState(
                stepId = step.stepId,
                stepName = step.stepName,
                stepIndex = step.stepIndex,
            )
        }
        val updated = current.update()
        val next = toMutableList()
        if (existingIndex >= 0) {
            next[existingIndex] = updated
        } else {
            next += updated
        }
        return next.sortedBy { it.stepIndex }
    }

    private fun JsonObject.decodeStepRef(): StepRef? = decodeFromPayload("step")

    private fun JsonObject.decodeOutputPayload(): OutputPayload? = decodeFromPayload("output")

    private fun JsonObject.decodePromptRequest(): PromptRequest? = decodeFromPayload("prompt")

    private fun JsonObject.decodeInteractionRequest(): InteractionRequest? = decodeFromPayload("interaction")

    private inline fun <reified T> JsonObject.decodeFromPayload(key: String): T? {
        val element = get(key) ?: return null
        return runCatching { json.decodeFromJsonElement<T>(element) }.getOrNull()
    }

    private fun JsonElement.asStringOrNull(): String? = (this as? JsonPrimitive)?.content

    private fun JsonElement.asIntOrNull(): Int? = (this as? JsonPrimitive)?.intOrNull

    private fun JsonElement.asBooleanOrNull(): Boolean? = (this as? JsonPrimitive)?.content?.toBooleanStrictOrNull()

    private fun currentStepStartLabel(): String = LocalTime.now().format(stepStartTimeFormatter)

    private fun normalizedOutputFormat(format: String): SemanticContentType = when (format) {
        else -> SemanticContentType.fromWireValue(format)
    }

    private fun decodeProgressItemState(
        output: OutputPayload,
        variant: SemanticContentVariant,
    ): ProgressItemState? {
        val progressId = output.metadata["progress_id"]?.asStringOrNull() ?: return null
        return ProgressItemState(
            progressId = progressId,
            message = output.content,
            state = ProgressLifecycleState.fromWireValue(output.metadata["state"]?.asStringOrNull()),
            variant = variant,
            indeterminate = output.metadata["indeterminate"]?.asBooleanOrNull() ?: true,
        )
    }

    private fun toSemanticOutputItem(
        sequence: Int,
        stepId: String?,
        stepName: String?,
        output: OutputPayload,
    ): SemanticContentItemState? {
        val format = normalizedOutputFormat(output.format)
        if (format == SemanticContentType.PROGRESS) {
            return null
        }
        return SemanticContentItemState(
            sequence = sequence,
            source = SemanticContentSource.OUTPUT,
            stepId = stepId,
            stepName = stepName,
            type = format,
            variant = SemanticContentVariant.fromWireValue(output.metadata["variant"]?.asStringOrNull()),
            title = output.title,
            content = output.content,
            metadata = output.metadata,
        )
    }

    private fun decodeInteractionOptions(element: JsonElement): List<InteractionOptionState> {
        val options = runCatching { json.decodeFromJsonElement<List<InteractionOption>>(element) }.getOrNull()
            ?: return emptyList()
        return options.map {
            InteractionOptionState(
                id = it.id,
                label = it.label,
                description = it.description,
                badges = it.badges,
            )
        }
    }

    private fun decodeItemReviewState(element: JsonElement): ItemReviewInteractionState? {
        val reviewState = runCatching { json.decodeFromJsonElement<ItemReviewState>(element) }.getOrNull()
            ?: return null
        return ItemReviewInteractionState(
            reviewId = reviewState.reviewId,
            items = reviewState.items.map { item ->
                ItemReviewItemState(
                    id = item.id,
                    title = item.title,
                    status = item.status,
                    contentItems = item.contentBlocks.mapIndexed { index, block ->
                        toSemanticContentItem(
                            sequence = index,
                            title = block.title,
                            content = block.content,
                            type = SemanticContentType.fromWireValue(block.type),
                            variant = SemanticContentVariant.fromWireValue(block.variant),
                            metadata = block.metadata,
                            source = SemanticContentSource.INTERACTION_CONTENT,
                        )
                    },
                    editable = item.editable,
                    visualState = ItemReviewItemVisualState.IDLE,
                    metadata = item.metadata,
                )
            },
            initialIndex = reviewState.initialIndex,
            allowedActions = reviewState.allowedActions,
            edit = reviewState.edit?.let {
                ItemReviewEditState(
                    enabled = it.enabled,
                    label = it.label,
                    initialValue = it.initialValue,
                )
            },
            metadata = reviewState.metadata,
        )
    }

    private fun toSemanticContentItem(
        sequence: Int,
        title: String?,
        content: String,
        type: SemanticContentType,
        variant: SemanticContentVariant,
        metadata: JsonObject,
        source: SemanticContentSource,
    ): SemanticContentItemState = SemanticContentItemState(
        sequence = sequence,
        source = source,
        type = type,
        variant = variant,
        title = title,
        content = content,
        metadata = metadata,
    )
}
