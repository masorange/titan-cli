package io.github.masorange.titan.desktop.state

import io.github.masorange.titan.desktop.protocol.EngineEventEnvelope
import io.github.masorange.titan.desktop.protocol.OutputPayload
import io.github.masorange.titan.desktop.protocol.PromptOption
import io.github.masorange.titan.desktop.protocol.PromptRequest
import io.github.masorange.titan.desktop.protocol.RunResult
import io.github.masorange.titan.desktop.protocol.StepRef
import io.github.masorange.titan.desktop.protocol.WorkflowDetail
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

    fun initialState(
        projectPath: String,
        workflowName: String,
        workflowDetail: WorkflowDetail? = null,
    ): WorkflowScreenState = WorkflowScreenState(
        header = RunHeaderState(
            workflowName = workflowDetail?.name ?: workflowName,
            workflowTitle = workflowDetail?.description,
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
        val timelineItems = runResult.steps.flatMapIndexed { index, step ->
            step.outputs.map { output ->
                OutputTimelineItemState(
                    sequence = index + 1,
                    stepId = step.id,
                    stepName = step.title,
                    format = output.format,
                    title = output.title,
                    content = output.content,
                )
            }
        }
        return state.copy(
            runId = runResult.runId,
            header = state.header.copy(
                workflowName = runResult.workflowName,
                status = runStatus,
                totalSteps = runResult.steps.size,
            ),
            steps = stepItems,
            timeline = if (state.timeline.isEmpty()) timelineItems else state.timeline,
            activePrompt = null,
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
            workflowTitle = event.payload["workflow_title"]?.asStringOrNull(),
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
                )
            },
            activePrompt = closePromptIfStepMatches(state.activePrompt, step.stepId),
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
                )
            },
            activePrompt = closePromptIfStepMatches(state.activePrompt, step.stepId),
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
                )
            },
            activePrompt = closePromptIfStepMatches(state.activePrompt, step.stepId),
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
                )
            },
            activePrompt = closePromptIfStepMatches(state.activePrompt, step.stepId),
        )
    }

    private fun reduceOutputEmitted(
        state: WorkflowScreenState,
        event: EngineEventEnvelope,
    ): WorkflowScreenState {
        val output = event.payload.decodeOutputPayload() ?: return state
        val step = event.payload.decodeStepRef()
        return state.copy(
            timeline = state.timeline + OutputTimelineItemState(
                sequence = event.sequence ?: state.timeline.size + 1,
                stepId = step?.stepId,
                stepName = step?.stepName,
                format = output.format,
                title = output.title,
                content = output.content,
            )
        )
    }

    private fun reducePromptRequested(
        state: WorkflowScreenState,
        event: EngineEventEnvelope,
    ): WorkflowScreenState {
        val prompt = event.payload.decodePromptRequest() ?: return state
        val step = event.payload.decodeStepRef()
        return state.copy(
            activePrompt = ActivePromptState(
                promptId = prompt.promptId,
                stepId = step?.stepId,
                stepName = step?.stepName,
                promptType = prompt.promptType,
                message = prompt.message,
                defaultValue = prompt.default,
                required = prompt.required,
                options = prompt.options,
            ),
            isRunActive = true,
        )
    }

    private fun reduceTerminalState(
        state: WorkflowScreenState,
        event: EngineEventEnvelope,
        status: RunVisualStatus,
    ): WorkflowScreenState = state.copy(
        header = state.header.copy(status = status),
        activePrompt = null,
        terminalMessage = event.payload["message"]?.asStringOrNull(),
        isRunActive = false,
        isTerminal = true,
    )

    private fun closePromptIfStepMatches(
        prompt: ActivePromptState?,
        stepId: String,
    ): ActivePromptState? {
        if (prompt?.stepId == stepId) {
            return null
        }
        return prompt
    }

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

    private inline fun <reified T> JsonObject.decodeFromPayload(key: String): T? {
        val element = get(key) ?: return null
        return runCatching { json.decodeFromJsonElement<T>(element) }.getOrNull()
    }

    private fun JsonElement.asStringOrNull(): String? = (this as? JsonPrimitive)?.content

    private fun JsonElement.asIntOrNull(): Int? = (this as? JsonPrimitive)?.intOrNull
}
