package io.github.masorange.titan.desktop.protocol

import kotlinx.serialization.json.JsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals

class PromptCommandEncoderTest {
    @Test
    fun `encode submit prompt response supports confirm prompts`() {
        val command = PromptCommandEncoder.encodeSubmitPromptResponse(
            runId = "run-123",
            promptId = "confirm-continue:confirm",
            value = JsonPrimitive(true),
        )

        assertEquals(
            "{" +
                "\"type\":\"submit_prompt_response\"," +
                "\"run_id\":\"run-123\"," +
                "\"payload\":{" +
                "\"prompt_id\":\"confirm-continue:confirm\"," +
                "\"value\":true}}",
            command,
        )
    }

    @Test
    fun `encode submit prompt response supports text prompts`() {
        val command = PromptCommandEncoder.encodeSubmitPromptResponse(
            runId = "run-123",
            promptId = "prompt-1",
            value = JsonPrimitive("hello"),
        )

        assertEquals(
            "{" +
                "\"type\":\"submit_prompt_response\"," +
                "\"run_id\":\"run-123\"," +
                "\"payload\":{" +
                "\"prompt_id\":\"prompt-1\"," +
                "\"value\":\"hello\"}}",
            command,
        )
    }
}
