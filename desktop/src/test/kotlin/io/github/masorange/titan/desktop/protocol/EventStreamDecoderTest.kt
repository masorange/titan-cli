package io.github.masorange.titan.desktop.protocol

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull

class EventStreamDecoderTest {
    @Test
    fun `decode event line parses valid V1 event`() {
        val event = EventStreamDecoder.decodeEventLine(
            """
            {"type":"run_started","run_id":"run-123","sequence":1,"timestamp":"2026-05-12T10:00:00Z","payload":{"workflow_name":"headless-v1-demo","project_path":"/repo","total_steps":3}}
            """.trimIndent()
        )

        val parsed = assertNotNull(event)
        assertEquals("run_started", parsed.type)
        assertEquals("run-123", parsed.runId)
        assertEquals(1, parsed.sequence)
    }

    @Test
    fun `decode event line returns null for invalid json`() {
        val event = EventStreamDecoder.decodeEventLine("not-json")

        assertNull(event)
    }
}
