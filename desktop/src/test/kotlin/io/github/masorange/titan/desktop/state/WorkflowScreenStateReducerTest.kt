package io.github.masorange.titan.desktop.state

import io.github.masorange.titan.desktop.protocol.EngineEventEnvelope
import io.github.masorange.titan.desktop.protocol.OutputPayload
import io.github.masorange.titan.desktop.protocol.RunResult
import io.github.masorange.titan.desktop.protocol.RunStepResult
import io.github.masorange.titan.desktop.protocol.WorkflowDetail
import io.github.masorange.titan.desktop.protocol.WorkflowStepSummary
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.add
import kotlinx.serialization.json.addJsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonPrimitive
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
    fun `initial state preloads pending steps from workflow detail`() {
        val state = WorkflowScreenStateReducer.initialState(
            projectPath = "/repo",
            workflowName = "commit-ai",
            workflowDetail = WorkflowDetail(
                name = "Commit with AI, Linter and Tests",
                description = "Create a commit with AI-generated message, with linting and testing.",
                source = "project",
                steps = listOf(
                    WorkflowStepSummary(id = "git_status", name = "Check Git Status", plugin = "git", step = "get_status"),
                    WorkflowStepSummary(id = "ruff-lint", name = "Run Ruff Linter", plugin = "project", step = "ruff_linter"),
                    WorkflowStepSummary(id = "diff_summary", name = "Show Changes Summary", plugin = "git", step = "show_uncommitted_diff_summary"),
                ),
            ),
        )

        assertEquals("Commit with AI, Linter and Tests", state.header.workflowName)
        assertEquals("Create a commit with AI-generated message, with linting and testing.", state.header.workflowTitle)
        assertEquals(3, state.header.totalSteps)
        assertEquals(3, state.steps.size)
        assertEquals(listOf("git_status", "ruff-lint", "diff_summary"), state.steps.map { it.stepId })
        assertTrue(state.steps.all { it.status == StepVisualStatus.PENDING })
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
        assertNotNull(started.steps.first().startedAtLabel)
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
    fun `output_emitted appends visible output item`() {
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
                        putJsonObject("metadata") {
                            put("kind", "plain")
                        }
                    }
                },
            ),
        )

        assertEquals(1, state.outputItems.size)
        assertEquals("emit-text", state.outputItems.first().stepId)
        assertEquals(OutputVisualFormat.TEXT, state.outputItems.first().format)
        assertEquals("plain", state.outputItems.first().metadata["kind"]?.jsonPrimitive?.content)
    }

    @Test
    fun `output_emitted preserves diff metadata for desktop rendering`() {
        val state = WorkflowScreenStateReducer.reduce(
            initialState,
            event(
                type = "output_emitted",
                sequence = 3,
                payload = buildJsonObject {
                    putJsonObject("step") {
                        put("step_id", "fetch_bundle")
                        put("step_name", "Fetch PR Review Bundle")
                        put("step_index", 1)
                    }
                    putJsonObject("output") {
                        put("format", "diff")
                        put("content", "diff --git a/foo.py b/foo.py")
                        put("title", "Files affected:")
                        putJsonObject("metadata") {
                            put("kind", "unified_patch")
                            putJsonArray("summary_lines") {
                                add(JsonPrimitive("1 file changed, 1 insertion(+), 0 deletions(-)"))
                            }
                        }
                    }
                },
            ),
        )

        assertEquals(OutputVisualFormat.DIFF, state.outputItems.first().format)
        assertEquals("unified_patch", state.outputItems.first().metadata["kind"]?.jsonPrimitive?.content)
    }

    @Test
    fun `output_emitted preserves structured summary metadata for desktop rendering`() {
        val state = WorkflowScreenStateReducer.reduce(
            initialState,
            event(
                type = "output_emitted",
                sequence = 3,
                payload = buildJsonObject {
                    putJsonObject("step") {
                        put("step_id", "classify_pr")
                        put("step_name", "Classify PR")
                        put("step_index", 1)
                    }
                    putJsonObject("output") {
                        put("format", "structured_summary")
                        put("content", "Size class: MEDIUM\nFiles changed: 12")
                        put("title", "PR Classification")
                        putJsonObject("metadata") {
                            put("kind", "pr_classification")
                            putJsonArray("summary_lines") {
                                add(JsonPrimitive("Size class: MEDIUM"))
                                add(JsonPrimitive("Files changed: 12"))
                            }
                            putJsonArray("sections") {
                                addJsonObject {
                                    put("title", "Scope")
                                    putJsonArray("lines") {
                                        add(JsonPrimitive("Lines changed: 184"))
                                    }
                                }
                            }
                        }
                    }
                },
            ),
        )

        assertEquals(OutputVisualFormat.STRUCTURED_SUMMARY, state.outputItems.first().format)
        assertEquals("pr_classification", state.outputItems.first().metadata["kind"]?.jsonPrimitive?.content)
        assertEquals(
            "Scope",
            state.outputItems.first().metadata["sections"]
                ?.toString()
                ?.let { if (it.contains("Scope")) "Scope" else null }
        )
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
    fun `interaction_requested opens active option list interaction`() {
        val state = WorkflowScreenStateReducer.reduce(
            initialState,
            event(
                type = "interaction_requested",
                sequence = 4,
                payload = buildJsonObject {
                    putJsonObject("step") {
                        put("step_id", "select_cli")
                        put("step_name", "Select AI CLI")
                        put("step_index", 2)
                    }
                    putJsonObject("interaction") {
                        put("interaction_id", "select-cli:select-cli")
                        put("interaction_type", "option_list")
                        put("message", "Choose CLI")
                        putJsonObject("state") {
                            putJsonArray("options") {
                                addJsonObject {
                                    put("id", "claude")
                                    put("label", "Claude")
                                    put("description", "Anthropic's Claude AI")
                                    putJsonArray("badges") {}
                                }
                            }
                        }
                        putJsonArray("actions") {}
                        putJsonObject("metadata") {}
                    }
                },
            ),
        )

        val interaction = assertNotNull(state.activeInteraction)
        assertEquals(InteractionVisualType.OPTION_LIST, interaction.interactionType)
        assertEquals("select-cli:select-cli", interaction.interactionId)
        assertEquals(1, interaction.options.size)
        assertEquals("claude", interaction.options.first().id)
    }

    @Test
    fun `step_finished closes active interaction for same step`() {
        val opened = WorkflowScreenStateReducer.reduce(
            initialState,
            event(
                type = "interaction_requested",
                sequence = 4,
                payload = buildJsonObject {
                    putJsonObject("step") {
                        put("step_id", "select_cli")
                        put("step_name", "Select AI CLI")
                        put("step_index", 2)
                    }
                    putJsonObject("interaction") {
                        put("interaction_id", "select-cli:select-cli")
                        put("interaction_type", "option_list")
                        putJsonObject("state") {
                            putJsonArray("options") {}
                        }
                        putJsonArray("actions") {}
                        putJsonObject("metadata") {}
                    }
                },
            ),
        )

        val finished = WorkflowScreenStateReducer.reduce(
            opened,
            stepEvent("step_finished", 5, "select_cli", "Select AI CLI", 2) {
                put("message", "done")
            },
        )

        assertNull(finished.activeInteraction)
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
        assertEquals(1, state.outputItems.size)
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
