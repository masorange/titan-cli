package io.github.masorange.titan.desktop.ui.components.interactions

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material.Button
import androidx.compose.material.MaterialTheme
import androidx.compose.material.OutlinedButton
import androidx.compose.material.Text
import androidx.compose.material.TextField
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import io.github.masorange.titan.desktop.state.ItemReviewDecisionState
import io.github.masorange.titan.desktop.state.ItemReviewEditState
import io.github.masorange.titan.desktop.state.ItemReviewInteractionState
import io.github.masorange.titan.desktop.state.ItemReviewItemState
import io.github.masorange.titan.desktop.state.ItemReviewItemVisualState
import io.github.masorange.titan.desktop.state.SemanticContentItemState
import io.github.masorange.titan.desktop.state.SemanticContentSource
import io.github.masorange.titan.desktop.state.SemanticContentType
import io.github.masorange.titan.desktop.state.SemanticContentVariant
import io.github.masorange.titan.desktop.theme.H3Text
import io.github.masorange.titan.desktop.theme.H4Text
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import io.github.masorange.titan.desktop.ui.DesktopPreview
import io.github.masorange.titan.desktop.ui.components.workflow.SemanticContentView
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun ItemReviewInteractionContainer(
    interactionId: String,
    state: ItemReviewInteractionState,
    isSubmitting: Boolean,
    onSubmitReview: (String, List<ItemReviewDecisionState>, Boolean) -> Unit,
    modifier: Modifier = Modifier,
) {
    val items = remember(interactionId) {
        mutableStateListOf<ItemReviewItemState>().apply {
            addAll(state.items)
            ensureActiveItem(this)
        }
    }

    if (items.isEmpty()) {
        Column(modifier = modifier.fillMaxWidth()) {
            H3Text(text = "No review items")
        }
        return
    }

    val decisions = remember(interactionId) { mutableStateListOf<ItemReviewDecisionState>() }
    val edits = remember(interactionId) { mutableStateMapOf<String, String>() }
    val currentItem = items.firstOrNull { it.visualState == ItemReviewItemVisualState.ACTIVE }
    var isEditing by remember(interactionId, currentItem?.id) { mutableStateOf(false) }

    if (currentItem == null) {
        Column(
            modifier = modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(Spacing.s5),
        ) {
            items.filter { it.visualState == ItemReviewItemVisualState.COMPLETED }.forEach { item ->
                CompletedItemReviewCard(
                    item = item,
                    decision = decisions.firstOrNull { it.itemId == item.id },
                )
            }
            H3Text(text = "Review complete")
        }
        return
    }

    val defaultEditValue = edits[currentItem.id]
        ?: state.edit?.initialValue
        ?: currentItem.contentItems.firstOrNull()?.content.orEmpty()

    val visibleItems = items.filter { it.visualState != ItemReviewItemVisualState.IDLE }

    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(Spacing.s5),
    ) {
        visibleItems.forEach { item ->
            val isCurrentItem = item.id == currentItem.id
            if (!isCurrentItem) {
                CompletedItemReviewCard(
                    item = item,
                    decision = decisions.firstOrNull { it.itemId == item.id },
                )
            } else {
                H3Text(text = item.title)

                item.status?.let {
                    H4Text(text = it.uppercase())
                }

                item.contentItems.forEach { contentItem ->
                    SemanticContentView(item = contentItem)
                }

                if (isEditing && item.editable && state.edit?.enabled == true) {
                    var editDraft by remember(interactionId, item.id) { mutableStateOf(defaultEditValue) }
                    Column(verticalArrangement = Arrangement.spacedBy(Spacing.s4)) {
                        TextField(
                            value = editDraft,
                            onValueChange = {
                                editDraft = it
                                edits[item.id] = it
                            },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text(state.edit.label ?: "Edit content") },
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(Spacing.s4)) {
                            Button(
                                onClick = {
                                    recordDecision(decisions, ItemReviewDecisionState(item.id, "edit", editDraft))
                                    isEditing = false
                                    advanceItemReview(items, item.id)
                                    if (items.none { it.visualState == ItemReviewItemVisualState.ACTIVE }) {
                                        onSubmitReview(interactionId, decisions.toList(), false)
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
                                    enabled = !isSubmitting && item.editable && state.edit?.enabled == true,
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
                                        recordDecision(decisions, ItemReviewDecisionState(item.id, action))
                                        advanceItemReview(items, item.id)
                                        if (items.none { it.visualState == ItemReviewItemVisualState.ACTIVE }) {
                                            onSubmitReview(interactionId, decisions.toList(), false)
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
    }
}

@Composable
private fun CompletedItemReviewCard(
    item: ItemReviewItemState,
    decision: ItemReviewDecisionState?,
) {
    Column(verticalArrangement = Arrangement.spacedBy(Spacing.s3)) {
        H3Text(text = item.title)
        item.status?.let {
            H4Text(text = it.uppercase())
        }
        item.contentItems.forEach { contentItem ->
            SemanticContentView(item = contentItem)
        }
        decision?.let {
            H4Text(text = "${it.action.uppercase()}${it.content?.takeIf(String::isNotBlank)?.let { content -> ": $content" } ?: ""}")
        }
    }
}

private fun ensureActiveItem(items: MutableList<ItemReviewItemState>) {
    if (items.any { it.visualState == ItemReviewItemVisualState.ACTIVE }) {
        return
    }

    val firstIdleIndex = items.indexOfFirst { it.visualState == ItemReviewItemVisualState.IDLE }
    if (firstIdleIndex >= 0) {
        items[firstIdleIndex] = items[firstIdleIndex].copy(visualState = ItemReviewItemVisualState.ACTIVE)
    }
}

private fun advanceItemReview(
    items: MutableList<ItemReviewItemState>,
    itemId: String,
) {
    val currentIndex = items.indexOfFirst { it.id == itemId }
    if (currentIndex < 0) {
        return
    }

    items[currentIndex] = items[currentIndex].copy(visualState = ItemReviewItemVisualState.COMPLETED)
    val nextIdleIndex = items.indexOfFirst { it.visualState == ItemReviewItemVisualState.IDLE }
    if (nextIdleIndex >= 0) {
        items[nextIdleIndex] = items[nextIdleIndex].copy(visualState = ItemReviewItemVisualState.ACTIVE)
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

@Preview
@Composable
private fun ItemReviewInteractionContainerPreview() {
    DesktopPreview {
        ItemReviewInteractionContainer(
            interactionId = "123",
            state = ItemReviewInteractionState(
                reviewId = "123",
                allowedActions = listOf("approve", "edit", "skip", "exit"),
                edit = ItemReviewEditState(
                    enabled = true,
                    label = "Edit review comment",
                    initialValue = "Consider guarding this branch when the payload is empty.",
                ),
                items = listOf(
                    ItemReviewItemState(
                        id = "comment-1",
                        title = "Comment 1 of 2",
                        status = "important",
                        editable = true,
                        visualState = ItemReviewItemVisualState.COMPLETED,
                        contentItems = listOf(
                            SemanticContentItemState(
                                sequence = 1,
                                source = SemanticContentSource.INTERACTION_CONTENT,
                                type = SemanticContentType.TEXT,
                                title = "Proposed action",
                                content = "Consider guarding this branch when the payload is empty.",
                            ),
                            SemanticContentItemState(
                                sequence = 2,
                                source = SemanticContentSource.INTERACTION_CONTENT,
                                type = SemanticContentType.STRUCTURED_SUMMARY,
                                title = "Action details",
                                content = "Possible null handling issue\nReasoning: The response may be empty here.\nLocation: src/foo.py:42\nSeverity: important",
                            ),
                            SemanticContentItemState(
                                sequence = 3,
                                source = SemanticContentSource.INTERACTION_CONTENT,
                                type = SemanticContentType.DIFF,
                                variant = SemanticContentVariant.MUTED,
                                title = "Relevant diff",
                                content = "@@ -38,6 +38,8 @@ fun handle(response: String?) {\n-    return response.length\n+    val safeResponse = response ?: return 0\n+    return safeResponse.length\n }",
                            ),
                        ),
                    ),
                    ItemReviewItemState(
                        id = "comment-2",
                        title = "Comment 2 of 2",
                        status = "thread",
                        editable = false,
                        contentItems = listOf(
                            SemanticContentItemState(
                                sequence = 4,
                                source = SemanticContentSource.INTERACTION_CONTENT,
                                type = SemanticContentType.TEXT,
                                title = "Proposed action",
                                content = "Resolve the outdated thread after confirming the latest patch covers it.",
                            ),
                            SemanticContentItemState(
                                sequence = 5,
                                source = SemanticContentSource.INTERACTION_CONTENT,
                                type = SemanticContentType.MARKDOWN,
                                title = "Thread context",
                                content = "- reviewer: Could this path crash when response is null?\n- author: I think the caller always provides one, but I can harden it.",
                            ),
                        ),
                    )
                ),
            ),
            isSubmitting = false,
            onSubmitReview = { _, _, _ -> },
        )
    }
}
