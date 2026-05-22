package io.github.masorange.titan.desktop

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class AppInteractionStateTest {
    @Test
    fun `interaction submitting clears when active interaction changes`() {
        val previousInteractionId = "select_pr:select-pr"
        val nextInteractionId = "select_cli:select-cli"

        val shouldRemainSubmitting = previousInteractionId == nextInteractionId

        assertFalse(shouldRemainSubmitting)
    }

    @Test
    fun `interaction submitting remains when same interaction stays active`() {
        val previousInteractionId = "select_pr:select-pr"
        val nextInteractionId = "select_pr:select-pr"

        val shouldRemainSubmitting = previousInteractionId == nextInteractionId

        assertTrue(shouldRemainSubmitting)
    }
}
