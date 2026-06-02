package io.github.masorange.titan.desktop.ui.components.interactions
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Spacer
import androidx.compose.material.Button
import androidx.compose.material.Card
import androidx.compose.material.Icon
import androidx.compose.material.MaterialTheme
import androidx.compose.material.OutlinedButton
import androidx.compose.material.Text
import androidx.compose.material.TextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.ItemReviewDecisionState
import io.github.masorange.titan.desktop.state.ItemReviewEditState
import io.github.masorange.titan.desktop.state.ItemReviewInteractionState
import io.github.masorange.titan.desktop.state.ItemReviewItemState
import io.github.masorange.titan.desktop.state.ItemReviewItemVisualState
import io.github.masorange.titan.desktop.state.SemanticContentType
import io.github.masorange.titan.desktop.state.SemanticContentItemState
import io.github.masorange.titan.desktop.state.SemanticContentSource
import io.github.masorange.titan.desktop.state.SemanticContentVariant
import io.github.masorange.titan.desktop.theme.H3Text
import io.github.masorange.titan.desktop.theme.H4Text
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import io.github.masorange.titan.desktop.ui.DesktopPreview
import io.github.masorange.titan.desktop.ui.LocalTheme
import io.github.masorange.titan.desktop.ui.components.workflow.SemanticContentView
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
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

    val decisions = remember(interactionId) { mutableStateListOf<ItemReviewDecisionState>() }
    val edits = remember(interactionId) { mutableStateMapOf<String, String>() }
    val activeItemId = items.firstOrNull { it.visualState == ItemReviewItemVisualState.ACTIVE }?.id
    var isEditing by remember(interactionId, activeItemId) { mutableStateOf(false) }
    val expandedStates = remember(interactionId) { mutableStateMapOf<String, Boolean>() }

    if (items.isEmpty()) {
        Column(modifier = modifier.fillMaxWidth()) {
            H3Text(text = "No review items")
        }
        return
    }

    val reviewItems = items.filter { it.visualState != ItemReviewItemVisualState.IDLE }
    val isReviewComplete = activeItemId == null

    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(Spacing.s5),
    ) {
        reviewItems.forEach { item ->
            val isActiveItem = item.id == activeItemId
            val isExpanded = expandedStates[item.id] ?: isActiveItem

            ReviewItemCard(
                item = item,
                isActiveItem = isActiveItem,
                isExpanded = isExpanded,
                onExpandedChange = { expandedStates[item.id] = it },
            ) {
                ReviewItemBody(
                    item = item,
                    decision = decisions.firstOrNull { it.itemId == item.id },
                    isActiveItem = isActiveItem,
                    interactionId = interactionId,
                    isSubmitting = isSubmitting,
                    isEditing = isEditing,
                    setEditing = { isEditing = it },
                    editLabel = state.edit?.label ?: "Edit content",
                    editInitialValue = state.edit?.initialValue,
                    editEnabled = state.edit?.enabled == true,
                    allowedActions = state.allowedActions,
                    edits = edits,
                    decisions = decisions,
                    onSubmitReview = onSubmitReview,
                    onDecision = { decision ->
                        recordDecision(decisions, decision)
                        expandedStates[item.id] = false
                        advanceItemReview(items, item.id)
                        items.firstOrNull { it.visualState == ItemReviewItemVisualState.ACTIVE }
                            ?.let { nextItem -> expandedStates[nextItem.id] = true }
                        if (items.none { it.visualState == ItemReviewItemVisualState.ACTIVE }) {
                            onSubmitReview(interactionId, decisions.toList(), false)
                        }
                    },
                )
            }
        }

        if (isReviewComplete) {
            H3Text(text = "Review complete")
        }
    }
}

@Composable
private fun ReviewItemCard(
    item: ItemReviewItemState,
    isActiveItem: Boolean,
    isExpanded: Boolean,
    onExpandedChange: (Boolean) -> Unit,
    content: @Composable () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column {
            ReviewItemCardHeader(
                title = item.title,
                subtitle = item.headerContextLabel(),
                isExpanded = isExpanded,
                onExpandedChange = onExpandedChange,
            )

            if (isExpanded || isActiveItem) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(LocalTheme.current.colors.ui.diffPreviewBackground)
                        .padding(Spacing.s6),
                    verticalArrangement = Arrangement.spacedBy(Spacing.s4),
                ) {
                    item.status?.let { status ->
                        SeverityBadge(label = status)
                    }
                    content()
                }
            }
        }
    }
}

@Composable
private fun ReviewItemBody(
    item: ItemReviewItemState,
    decision: ItemReviewDecisionState?,
    isActiveItem: Boolean,
    interactionId: String,
    isSubmitting: Boolean,
    isEditing: Boolean,
    setEditing: (Boolean) -> Unit,
    editLabel: String,
    editInitialValue: String?,
    editEnabled: Boolean,
    allowedActions: List<String>,
    edits: MutableMap<String, String>,
    decisions: List<ItemReviewDecisionState>,
    onSubmitReview: (String, List<ItemReviewDecisionState>, Boolean) -> Unit,
    onDecision: (ItemReviewDecisionState) -> Unit,
) {
    val defaultEditValue = edits[item.id]
        ?: editInitialValue
        ?: item.contentItems.firstOrNull()?.content.orEmpty()

    val focusedDiffItems = item.contentItems.filter {
        it.type == SemanticContentType.DIFF && it.metadata.diffType() == "focused_hunk"
    }
    val aiCommentItems = item.contentItems.filter {
        it.type == SemanticContentType.MARKDOWN && it.metadata.stringValue("role") == "ai_comment"
    }
    val threadContextItems = item.contentItems.filter {
        it.type == SemanticContentType.MARKDOWN && it.metadata.stringValue("role") == "thread_context"
    }
    val supportingItems = item.contentItems.filterNot {
        it in focusedDiffItems || it in aiCommentItems || it in threadContextItems
    }

    Column(verticalArrangement = Arrangement.spacedBy(Spacing.s3)) {
        focusedDiffItems.forEach { contentItem ->
            SemanticContentView(item = contentItem)
        }

        aiCommentItems.forEach { contentItem ->
            SemanticContentView(
                item = contentItem.copy(
                    type = SemanticContentType.MARKDOWN,
                    title = "AI comment",
                )
            )
        }

        threadContextItems.forEach { contentItem ->
            SemanticContentView(item = contentItem)
        }

        supportingItems.forEach { contentItem ->
            SemanticContentView(item = contentItem)
        }

        decision?.let {
            H4Text(
                text = "${it.action.uppercase()}${
                    it.content?.takeIf(String::isNotBlank)?.let { content -> ": $content" } ?: ""
                }")
        }

        if (isActiveItem) {
            if (isEditing && item.editable && editEnabled) {
                ReviewItemEditForm(
                    interactionId = interactionId,
                    item = item,
                    defaultEditValue = defaultEditValue,
                    editLabel = editLabel,
                    isSubmitting = isSubmitting,
                    edits = edits,
                    onCancel = { setEditing(false) },
                    onSave = { editDraft ->
                        onDecision(ItemReviewDecisionState(item.id, "edit", editDraft))
                        setEditing(false)
                    },
                )
            } else {
                ReviewItemActions(
                    item = item,
                    allowedActions = allowedActions,
                    isSubmitting = isSubmitting,
                    editEnabled = editEnabled,
                    decisions = decisions,
                    interactionId = interactionId,
                    onSubmitReview = onSubmitReview,
                    onEdit = { setEditing(true) },
                    onDecision = onDecision,
                )
            }
        }
    }
}

@Composable
private fun ReviewItemEditForm(
    interactionId: String,
    item: ItemReviewItemState,
    defaultEditValue: String,
    editLabel: String,
    isSubmitting: Boolean,
    edits: MutableMap<String, String>,
    onCancel: () -> Unit,
    onSave: (String) -> Unit,
) {
    var editDraft by remember(interactionId, item.id) { mutableStateOf(defaultEditValue) }

    Column(verticalArrangement = Arrangement.spacedBy(Spacing.s4)) {
        TextField(
            value = editDraft,
            onValueChange = {
                editDraft = it
                edits[item.id] = it
            },
            modifier = Modifier.fillMaxWidth(),
            label = { Text(editLabel) },
        )
        Row(horizontalArrangement = Arrangement.spacedBy(Spacing.s4)) {
            Button(
                onClick = { onSave(editDraft) },
                enabled = !isSubmitting && editDraft.isNotBlank(),
            ) {
                Text(if (isSubmitting) "Submitting..." else "Save and continue")
            }
            OutlinedButton(onClick = onCancel, enabled = !isSubmitting) {
                Text("Cancel")
            }
        }
    }
}

@Composable
private fun ReviewItemActions(
    item: ItemReviewItemState,
    allowedActions: List<String>,
    isSubmitting: Boolean,
    editEnabled: Boolean,
    decisions: List<ItemReviewDecisionState>,
    interactionId: String,
    onSubmitReview: (String, List<ItemReviewDecisionState>, Boolean) -> Unit,
    onEdit: () -> Unit,
    onDecision: (ItemReviewDecisionState) -> Unit,
) {
    Row(horizontalArrangement = Arrangement.spacedBy(Spacing.s4)) {
        allowedActions.forEach { action ->
            when (action) {
                "edit" -> OutlinedButton(
                    onClick = onEdit,
                    enabled = !isSubmitting && item.editable && editEnabled,
                ) {
                    Text("Edit")
                }

                "exit" -> OutlinedButton(
                    onClick = { onSubmitReview(interactionId, decisions, true) },
                    enabled = !isSubmitting,
                ) {
                    Text("Exit")
                }

                else -> OutlinedButton(
                    onClick = { onDecision(ItemReviewDecisionState(item.id, action)) },
                    enabled = !isSubmitting,
                ) {
                    Text(action.replaceFirstChar { it.uppercase() })
                }
            }
        }
    }
}

@Composable
private fun ReviewItemCardHeader(
    title: String,
    subtitle: String? = null,
    isExpanded: Boolean,
    onExpandedChange: (Boolean) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(LocalTheme.current.colors.ui.workflowHeaderBackground)
            .clickable { onExpandedChange(!isExpanded) }
            .padding(Spacing.s6),
        horizontalArrangement = Arrangement.spacedBy(Spacing.s4),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(Spacing.s1),
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.subtitle1,
                fontWeight = FontWeight.SemiBold,
            )
            subtitle?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.caption,
                    color = LocalTheme.current.colors.palette.text.secondary,
                    maxLines = Int.MAX_VALUE,
                    overflow = TextOverflow.Clip,
                )
            }
        }
        Icon(
            imageVector = if (isExpanded) {
                Icons.Filled.KeyboardArrowUp
            } else {
                Icons.Filled.KeyboardArrowDown
            },
            contentDescription = if (isExpanded) "Collapse step" else "Expand step",
            tint = MaterialTheme.colors.onSurface.copy(alpha = 0.7f),
        )
    }
}

private fun ItemReviewItemState.headerContextLabel(): String {
    val diffItem = contentItems.firstOrNull {
        it.type == SemanticContentType.DIFF && it.metadata.diffType() == "focused_hunk"
    }
    val path = diffItem?.metadata?.stringValue("path")
    val lineLabel = diffItem?.metadata?.stringValue("line_label")

    if (path == null && lineLabel == null) {
        return "General comment"
    }

    return listOfNotNull(path, lineLabel).joinToString("  ")
}

@Composable
private fun SeverityBadge(label: String) {
    val colors = LocalTheme.current.colors
    val borderColor = when (label.lowercase()) {
        "blocking" -> colors.palette.error.main
        "important" -> colors.palette.warning.main
        "nit" -> colors.palette.primary.main
        else -> colors.palette.text.secondary
    }

    Card(
        elevation = 0.dp,
        shape = RoundedCornerShape(Spacing.s4),
        border = BorderStroke(1.dp, borderColor),
        backgroundColor = MaterialTheme.colors.surface,
    ) {
        Text(
            text = label.uppercase(),
            modifier = Modifier.padding(horizontal = Spacing.s4, vertical = Spacing.s2),
            style = MaterialTheme.typography.caption,
            color = borderColor,
        )
    }
}

private fun kotlinx.serialization.json.JsonObject.diffType(): String? =
    (this["type"] as? JsonPrimitive)?.contentOrNull

private fun kotlinx.serialization.json.JsonObject.stringValue(key: String): String? =
    (this[key] as? JsonPrimitive)?.contentOrNull

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
                allowedActions = listOf("approve", "edit", "skip"),
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
                        visualState = ItemReviewItemVisualState.IDLE,
                        contentItems = listOf(
                            SemanticContentItemState(
                                sequence = 1,
                                source = SemanticContentSource.INTERACTION_CONTENT,
                                type = SemanticContentType.DIFF,
                                variant = SemanticContentVariant.MUTED,
                                title = "Relevant diff",
                                content = "@@ -38,6 +38,8 @@ fun handle(response: String?) {\n-    return response.length\n+    val safeResponse = response ?: return 0\n+    return safeResponse.length\n }",
                                metadata = buildJsonObject {
                                    put("type", "focused_hunk")
                                    put("path", "app/src/main/kotlin/example/Foo.kt")
                                    put("line_label", "Line 42 (AI 74 via snippet)")
                                    put("line", 42)
                                    put("original_line", 74)
                                    put("resolved_line", 42)
                                    put("resolution_source", "snippet")
                                },
                            ),
                            SemanticContentItemState(
                                sequence = 2,
                                source = SemanticContentSource.INTERACTION_CONTENT,
                                type = SemanticContentType.MARKDOWN,
                                title = "Proposed action",
                                content = "This symbol should be derived with the same locale used by `formatCurrency(...)` or extracted from the formatted string. Right now `currency.symbol` uses the JVM default locale, so on mixed-locale devices the substring match can fail and the currency symbol won't receive `currencyStyle`.",
                                metadata = buildJsonObject {
                                    put("role", "ai_comment")
                                },
                            ),
                        ),
                    ),
                    ItemReviewItemState(
                        id = "comment-2",
                        title = "Comment 2 of 2",
                        status = "thread",
                        editable = false,
                        visualState = ItemReviewItemVisualState.ACTIVE,
                        contentItems = listOf(
                            SemanticContentItemState(
                                sequence = 4,
                                source = SemanticContentSource.INTERACTION_CONTENT,
                                type = SemanticContentType.DIFF,
                                variant = SemanticContentVariant.MUTED,
                                title = "Relevant diff",
                                content = "@@ -24,6 +24,7 @@ fun QuantityWithCurrencyItem(\n-    val quantitySymbol = currency.symbol\n+    val quantitySymbol = currency.symbol\n+    val quantityText = formatCurrency(quantity, currency)\n ",
                                metadata = buildJsonObject {
                                    put("type", "focused_hunk")
                                    put("path", "app/src/main/kotlin/com/ragnarok/apps/ui/components/QuantityWithCurrency.kt")
                                    put("line_label", "Line 32 (AI 74 via snippet)")
                                    put("line", 32)
                                    put("original_line", 74)
                                    put("resolved_line", 32)
                                    put("resolution_source", "snippet")
                                },
                            ),
                            SemanticContentItemState(
                                sequence = 4,
                                source = SemanticContentSource.INTERACTION_CONTENT,
                                type = SemanticContentType.MARKDOWN,
                                title = "Proposed action",
                                content = "This symbol should be derived with the same locale used by `formatCurrency(...)` or extracted from the formatted string. Right now `formatCurrency` uses the app locale, but `currency.symbol` uses the JVM default locale, so on mixed-locale devices the substring match can fail and the currency symbol won't receive `currencyStyle`.",
                                metadata = buildJsonObject {
                                    put("role", "ai_comment")
                                },
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
