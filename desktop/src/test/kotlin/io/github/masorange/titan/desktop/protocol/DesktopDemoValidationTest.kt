package io.github.masorange.titan.desktop.protocol

import io.github.masorange.titan.desktop.state.RunVisualStatus
import io.github.masorange.titan.desktop.state.StepVisualStatus
import io.github.masorange.titan.desktop.state.WorkflowScreenState
import io.github.masorange.titan.desktop.state.WorkflowScreenStateReducer
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class DesktopDemoValidationTest {
    @Test
    fun `desktop validation flow completes through streamed run result`() {
        val finalState = applyEventLines(
            listOf(
                """
                {"type":"run_started","run_id":"run-123","sequence":1,"payload":{"workflow_name":"headless-v1-demo","workflow_title":"Headless V1 Demo","project_path":"/repo","total_steps":3}}
                """.trimIndent(),
                """
                {"type":"step_started","run_id":"run-123","sequence":2,"payload":{"step":{"step_id":"emit-text","step_name":"Emit Text","step_index":1},"plugin":"project","step_kind":"plugin"}}
                """.trimIndent(),
                """
                {"type":"output_emitted","run_id":"run-123","sequence":3,"payload":{"step":{"step_id":"emit-text","step_name":"Emit Text","step_index":1},"output":{"format":"text","title":"Text output","content":"demo text output","metadata":{}}}}
                """.trimIndent(),
                """
                {"type":"step_finished","run_id":"run-123","sequence":4,"payload":{"step":{"step_id":"emit-text","step_name":"Emit Text","step_index":1},"status":"success","message":"done","metadata":{}}}
                """.trimIndent(),
                """
                {"type":"step_started","run_id":"run-123","sequence":5,"payload":{"step":{"step_id":"confirm-continue","step_name":"Confirm Continue","step_index":2},"plugin":"project","step_kind":"plugin"}}
                """.trimIndent(),
                """
                {"type":"prompt_requested","run_id":"run-123","sequence":6,"payload":{"step":{"step_id":"confirm-continue","step_name":"Confirm Continue","step_index":2},"prompt":{"prompt_id":"confirm-continue:confirm","prompt_type":"confirm","message":"Continue headless demo?","default":true,"required":true,"options":[]}}}
                """.trimIndent(),
                """
                {"type":"step_finished","run_id":"run-123","sequence":7,"payload":{"step":{"step_id":"confirm-continue","step_name":"Confirm Continue","step_index":2},"status":"success","message":"confirmed","metadata":{}}}
                """.trimIndent(),
                """
                {"type":"step_started","run_id":"run-123","sequence":8,"payload":{"step":{"step_id":"emit-markdown","step_name":"Emit Markdown","step_index":3},"plugin":"project","step_kind":"plugin"}}
                """.trimIndent(),
                """
                {"type":"output_emitted","run_id":"run-123","sequence":9,"payload":{"step":{"step_id":"emit-markdown","step_name":"Emit Markdown","step_index":3},"output":{"format":"markdown","title":"Markdown output","content":"# Demo complete","metadata":{}}}}
                """.trimIndent(),
                """
                {"type":"step_finished","run_id":"run-123","sequence":10,"payload":{"step":{"step_id":"emit-markdown","step_name":"Emit Markdown","step_index":3},"status":"success","message":"done","metadata":{}}}
                """.trimIndent(),
                """
                {"type":"run_completed","run_id":"run-123","sequence":11,"payload":{"message":"Workflow completed successfully"}}
                """.trimIndent(),
                """
                {"type":"run_result_emitted","run_id":"run-123","sequence":12,"payload":{"run_result":{"run_id":"run-123","workflow_name":"headless-v1-demo","status":"completed","steps":[{"id":"emit-text","title":"Emit Text","status":"success","plugin":"project","error":null,"outputs":[{"format":"text","title":"Text output","content":"demo text output","metadata":{}}],"metadata":{}},{"id":"confirm-continue","title":"Confirm Continue","status":"success","plugin":"project","error":null,"outputs":[],"metadata":{}},{"id":"emit-markdown","title":"Emit Markdown","status":"success","plugin":"project","error":null,"outputs":[{"format":"markdown","title":"Markdown output","content":"# Demo complete","metadata":{}}],"metadata":{}}],"result":{"format":"markdown","title":"Markdown output","content":"# Demo complete","metadata":{}},"diagnostics":{"result_message":"Workflow 'Headless V1 Demo' finished.","pending_prompt_id":null}}}}
                """.trimIndent(),
            )
        )

        assertEquals(RunVisualStatus.COMPLETED, finalState.header.status)
        assertEquals(3, finalState.steps.size)
        assertEquals(StepVisualStatus.SUCCESS, finalState.steps.last().status)
        assertEquals(2, finalState.timeline.size)
        assertEquals("# Demo complete", finalState.timeline.last().content)
        assertNull(finalState.activePrompt)
        assertTrue(finalState.isTerminal)
        assertFalse(finalState.isRunActive)
    }

    @Test
    fun `desktop validation flow handles cancelled branch through streamed run result`() {
        val finalState = applyEventLines(
            listOf(
                """
                {"type":"run_started","run_id":"run-123","sequence":1,"payload":{"workflow_name":"headless-v1-demo","workflow_title":"Headless V1 Demo","project_path":"/repo","total_steps":3}}
                """.trimIndent(),
                """
                {"type":"step_started","run_id":"run-123","sequence":2,"payload":{"step":{"step_id":"confirm-continue","step_name":"Confirm Continue","step_index":2},"plugin":"project","step_kind":"plugin"}}
                """.trimIndent(),
                """
                {"type":"prompt_requested","run_id":"run-123","sequence":3,"payload":{"step":{"step_id":"confirm-continue","step_name":"Confirm Continue","step_index":2},"prompt":{"prompt_id":"confirm-continue:confirm","prompt_type":"confirm","message":"Continue headless demo?","default":true,"required":true,"options":[]}}}
                """.trimIndent(),
                """
                {"type":"run_cancelled","run_id":"run-123","sequence":4,"payload":{"message":"user_cancelled_demo"}}
                """.trimIndent(),
                """
                {"type":"run_result_emitted","run_id":"run-123","sequence":5,"payload":{"run_result":{"run_id":"run-123","workflow_name":"headless-v1-demo","status":"cancelled","steps":[{"id":"confirm-continue","title":"Confirm Continue","status":"failed","plugin":"project","error":"user_cancelled_demo","outputs":[],"metadata":{}}],"result":null,"diagnostics":{"result_message":"user_cancelled_demo","pending_prompt_id":null}}}}
                """.trimIndent(),
            )
        )

        assertEquals(RunVisualStatus.CANCELLED, finalState.header.status)
        assertTrue(finalState.isTerminal)
        assertFalse(finalState.isRunActive)
        assertNull(finalState.activePrompt)
        assertEquals("user_cancelled_demo", finalState.terminalMessage)
    }

    private fun applyEventLines(lines: List<String>): WorkflowScreenState {
        var state = WorkflowScreenStateReducer.initialState(
            projectPath = "/repo",
            workflowName = "headless-v1-demo",
        )

        lines.forEach { line ->
            val event = assertNotNull(EventStreamDecoder.decodeEventLine(line))
            if (event.type == "run_result_emitted") {
                val runResult = assertNotNull(EventStreamDecoder.decodeRunResultPayload(event))
                state = WorkflowScreenStateReducer.applyRunResult(state, runResult)
            } else {
                state = WorkflowScreenStateReducer.reduce(state, event)
            }
        }

        return state
    }
}
