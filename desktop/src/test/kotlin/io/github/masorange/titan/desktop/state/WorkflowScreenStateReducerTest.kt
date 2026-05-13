package io.github.masorange.titan.desktop.state

import io.github.masorange.titan.desktop.protocol.EngineEventEnvelope
import io.github.masorange.titan.desktop.protocol.OutputPayload
import io.github.masorange.titan.desktop.protocol.RunResult
import io.github.masorange.titan.desktop.protocol.RunStepResult
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.putJsonObject
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class WorkflowScreenStateReducerTest {
    private val initialState = WorkflowScreenStateReducer.initialState(
        projectPath = "/repo",
        workflowName = "headless-v1-demo",
    )

    @Test
    fun `run_started initializes header`() {
        val state = WorkflowScreenStateReducer.reduce(
            initialState,
            event(
                type = "run_started",
                sequence = 1,
                payload = buildJsonObject {
                    put("workflow_name", "headless-v1-demo")
                    put("workflow_title", "Headless V1 Demo")
                    put("project_path", "/repo")
                    put("total_steps", 3)
                },
            ),
        )

        assertEquals("run-123", state.runId)
        assertEquals(RunVisualStatus.RUNNING, state.header.status)
        assertEquals("Headless V1 Demo", state.header.workflowTitle)
        assertEquals(3, state.header.totalSteps)
        assertTrue(state.isRunActive)
    }

    @Test
    fun `step lifecycle updates state by step ref`() {
        val started = WorkflowScreenStateReducer.reduce(
            initialState,
            stepEvent("step_started", 1, "emit-text", "Emit Text", 1),
        )
        val finished = WorkflowScreenStateReducer.reduce(
            started,
            stepEvent("step_finished", 2, "emit-text", "Emit Text", 1) {
                put("message", "done")
            },
        )

        assertEquals(1, started.steps.size)
        assertEquals(StepVisualStatus.RUNNING, started.steps.first().status)
        assertEquals(StepVisualStatus.SUCCESS, finished.steps.first().status)
        assertEquals("done", finished.steps.first().message)
    }

    @Test
    fun `step failed and skipped are reflected`() {
        val failed = WorkflowScreenStateReducer.reduce(
            initialState,
            stepEvent("step_failed", 1, "confirm", "Confirm", 2) {
                put("message", "boom")
            },
        )
        val skipped = WorkflowScreenStateReducer.reduce(
            failed,
            stepEvent("step_skipped", 2, "emit-markdown", "Emit Markdown", 3) {
                put("message", "not needed")
            },
        )

        assertEquals(StepVisualStatus.FAILED, skipped.steps.first { it.stepId == "confirm" }.status)
        assertEquals(StepVisualStatus.SKIPPED, skipped.steps.first { it.stepId == "emit-markdown" }.status)
    }

    @Test
    fun `output_emitted appends visible timeline item`() {
        val state = WorkflowScreenStateReducer.reduce(
            initialState,
            event(
                type = "output_emitted",
                sequence = 3,
                payload = buildJsonObject {
                    putJsonObject("step") {
                        put("step_id", "emit-text")
                        put("step_name", "Emit Text")
                        put("step_index", 1)
                    }
                    putJsonObject("output") {
                        put("format", "text")
                        put("content", "demo text output")
                        put("title", "Text output")
                        putJsonObject("metadata") {}
                    }
                },
            ),
        )

        assertEquals(1, state.timeline.size)
        assertEquals("emit-text", state.timeline.first().stepId)
        assertEquals("text", state.timeline.first().format)
    }

    @Test
    fun `prompt_requested opens active prompt`() {
        val state = WorkflowScreenStateReducer.reduce(
            initialState,
            event(
                type = "prompt_requested",
                sequence = 4,
                payload = buildJsonObject {
                    putJsonObject("step") {
                        put("step_id", "confirm-continue")
                        put("step_name", "Confirm Continue")
                        put("step_index", 2)
                    }
                    putJsonObject("prompt") {
                        put("prompt_id", "confirm-continue:confirm")
                        put("prompt_type", "confirm")
                        put("message", "Continue?")
                        put("default", true)
                        put("required", true)
                        putJsonArray("options") {}
                    }
                },
            ),
        )

        val prompt = assertNotNull(state.activePrompt)
        assertEquals("confirm", prompt.promptType)
        assertEquals("confirm-continue:confirm", prompt.promptId)
    }

    @Test
    fun `terminal run closes active prompt`() {
        val prompted = WorkflowScreenStateReducer.reduce(
            initialState,
            event(
                type = "prompt_requested",
                sequence = 4,
                payload = buildJsonObject {
                    putJsonObject("step") {
                        put("step_id", "confirm-continue")
                        put("step_name", "Confirm Continue")
                        put("step_index", 2)
                    }
                    putJsonObject("prompt") {
                        put("prompt_id", "confirm-continue:confirm")
                        put("prompt_type", "confirm")
                        put("message", "Continue?")
                        put("required", true)
                        putJsonArray("options") {}
                    }
                },
            ),
        )
        val terminal = WorkflowScreenStateReducer.reduce(
            prompted,
            event(
                type = "run_completed",
                sequence = 5,
                payload = buildJsonObject {
                    put("message", "Workflow completed successfully")
                },
            ),
        )

        assertNull(terminal.activePrompt)
        assertEquals(RunVisualStatus.COMPLETED, terminal.header.status)
        assertFalse(terminal.isRunActive)
        assertTrue(terminal.isTerminal)
    }

    @Test
    fun `apply run result consolidates terminal snapshot`() {
        val state = WorkflowScreenStateReducer.applyRunResult(
            initialState,
            RunResult(
                runId = "run-123",
                workflowName = "headless-v1-demo",
                status = "completed",
                steps = listOf(
                    RunStepResult(
                        id = "emit-text",
                        title = "Emit Text",
                        status = "success",
                        plugin = "project",
                        outputs = listOf(
                            OutputPayload(
                                format = "text",
                                title = "Text output",
                                content = "demo text output",
                            )
                        ),
                    ),
                    RunStepResult(
                        id = "emit-markdown",
                        title = "Emit Markdown",
                        status = "success",
                        plugin = "project",
                    ),
                ),
                diagnostics = buildJsonObject {
                    put("result_message", "Workflow finished")
                },
            ),
        )

        assertEquals(RunVisualStatus.COMPLETED, state.header.status)
        assertEquals(2, state.steps.size)
        assertEquals(1, state.timeline.size)
        assertEquals("Workflow finished", state.terminalMessage)
        assertTrue(state.isTerminal)
    }

    private fun event(
        type: String,
        sequence: Int,
        payload: JsonObject,
    ) = EngineEventEnvelope(
        type = type,
        runId = "run-123",
        sequence = sequence,
        payload = payload,
    )

    private fun stepEvent(
        type: String,
        sequence: Int,
        stepId: String,
        stepName: String,
        stepIndex: Int,
        extraPayload: kotlinx.serialization.json.JsonObjectBuilder.() -> Unit = {},
    ) = event(
        type = type,
        sequence = sequence,
        payload = buildJsonObject {
            putJsonObject("step") {
                put("step_id", stepId)
                put("step_name", stepName)
                put("step_index", stepIndex)
            }
            extraPayload()
        },
    )
}
