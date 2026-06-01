package io.github.masorange.titan.desktop.ui.components.interactions

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.Button
import androidx.compose.material.MaterialTheme
import androidx.compose.material.OutlinedButton
import androidx.compose.material.Text
import androidx.compose.material.TextField
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import io.github.masorange.titan.desktop.state.ItemReviewDecisionState
import io.github.masorange.titan.desktop.state.ItemReviewInteractionState
import io.github.masorange.titan.desktop.theme.H3Text
import io.github.masorange.titan.desktop.theme.H4Text
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import io.github.masorange.titan.desktop.ui.components.content.ContentBlockView

@Composable
fun ItemReviewInteractionPanel(
    interactionId: String,
    state: ItemReviewInteractionState,
    isSubmitting: Boolean,
    onSubmitReview: (String, List<ItemReviewDecisionState>, Boolean) -> Unit,
    modifier: Modifier = Modifier,
) {
    val items = state.items
    if (items.isEmpty()) {
        Column(modifier = modifier.fillMaxWidth()) {
            H3Text(text = "No review items")
        }
        return
    }

    var currentIndex by remember(interactionId) { mutableIntStateOf(state.initialIndex.coerceIn(0, items.lastIndex)) }
    val decisions = remember(interactionId) { mutableStateListOf<ItemReviewDecisionState>() }
    val edits = remember(interactionId) { mutableStateMapOf<String, String>() }
    var isEditing by remember(interactionId, currentIndex) { mutableStateOf(false) }

    val currentItem = items[currentIndex]
    val defaultEditValue = edits[currentItem.id]
        ?: state.edit?.initialValue
        ?: currentItem.contentBlocks.firstOrNull()?.content.orEmpty()

    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(Spacing.s5),
    ) {
        H3Text(text = currentItem.title)
        Text(
            text = "${currentIndex + 1} of ${items.size}",
            style = MaterialTheme.typography.caption,
        )
        currentItem.status?.let { H4Text(text = it) }

        currentItem.contentBlocks.forEach { block ->
            ContentBlockView(block = block)
        }

        if (isEditing && currentItem.editable && state.edit?.enabled == true) {
            var editDraft by remember(interactionId, currentItem.id) { mutableStateOf(defaultEditValue) }
            Column(verticalArrangement = Arrangement.spacedBy(Spacing.s4)) {
                TextField(
                    value = editDraft,
                    onValueChange = {
                        editDraft = it
                        edits[currentItem.id] = it
                    },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text(state.edit.label ?: "Edit content") },
                )
                Row(horizontalArrangement = Arrangement.spacedBy(Spacing.s4)) {
                    Button(
                        onClick = {
                            recordDecision(decisions, ItemReviewDecisionState(currentItem.id, "edit", editDraft))
                            isEditing = false
                            if (currentIndex == items.lastIndex) {
                                onSubmitReview(interactionId, decisions.toList(), false)
                            } else {
                                currentIndex += 1
                            }
                        },
                        enabled = !isSubmitting && editDraft.isNotBlank(),
                    ) {
                        Text(if (isSubmitting) "Submitting..." else "Save and continue")
                    }
                    OutlinedButton(onClick = { isEditing = false }, enabled = !isSubmitting) {
                        Text("Cancel")
                    }
                }
            }
        } else {
            Row(horizontalArrangement = Arrangement.spacedBy(Spacing.s4)) {
                state.allowedActions.forEach { action ->
                    when (action) {
                        "edit" -> OutlinedButton(
                            onClick = { isEditing = true },
                            enabled = !isSubmitting && currentItem.editable && state.edit?.enabled == true,
                        ) {
                            Text("Edit")
                        }

                        "exit" -> OutlinedButton(
                            onClick = { onSubmitReview(interactionId, decisions.toList(), true) },
                            enabled = !isSubmitting,
                        ) {
                            Text("Exit")
                        }

                        else -> OutlinedButton(
                            onClick = {
                                recordDecision(decisions, ItemReviewDecisionState(currentItem.id, action))
                                if (currentIndex == items.lastIndex) {
                                    onSubmitReview(interactionId, decisions.toList(), false)
                                } else {
                                    currentIndex += 1
                                }
                            },
                            enabled = !isSubmitting,
                        ) {
                            Text(action.replaceFirstChar { it.uppercase() })
                        }
                    }
                }
            }
        }
    }
}

private fun recordDecision(
    decisions: MutableList<ItemReviewDecisionState>,
    decision: ItemReviewDecisionState,
) {
    val existingIndex = decisions.indexOfFirst { it.itemId == decision.itemId }
    if (existingIndex >= 0) {
        decisions[existingIndex] = decision
    } else {
        decisions += decision
    }
}
