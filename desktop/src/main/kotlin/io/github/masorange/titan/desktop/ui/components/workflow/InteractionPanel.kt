package io.github.masorange.titan.desktop.ui.components.workflow

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.Card
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.ActiveInteractionState
import io.github.masorange.titan.desktop.state.InteractionVisualType
import io.github.masorange.titan.desktop.theme.H2Text
import io.github.masorange.titan.desktop.ui.DesktopPreview
import io.github.masorange.titan.desktop.ui.components.interactions.ItemReviewInteractionContainer
import io.github.masorange.titan.desktop.ui.components.interactions.OptionListInteractionPanel
import org.jetbrains.compose.ui.tooling.preview.Preview
import io.github.masorange.titan.desktop.state.InteractionOptionState
import io.github.masorange.titan.desktop.state.ItemReviewDecisionState
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import io.github.masorange.titan.desktop.ui.LocalTheme

@Composable
fun InteractionPanel(
    modifier: Modifier = Modifier,
    interaction: ActiveInteractionState?,
    isSubmitting: Boolean,
    onSelectInteractionOption: (String, String) -> Unit = { _, _ -> },
    onSubmitItemReview: (String, List<ItemReviewDecisionState>, Boolean) -> Unit = { _, _, _ -> },
) {
    Column(modifier = modifier.fillMaxWidth()) {
        if (interaction == null) {
            Column(modifier = Modifier.fillMaxWidth().background(LocalTheme.current.colors.palette.background.default)) {
                H2Text(
                    modifier = Modifier.padding(Spacing.s6),
                    text = "No active interaction"
                )
            }

        }

        interaction?.interactionType?.let { type ->
            when (type) {
                InteractionVisualType.OPTION_LIST -> {
                    OptionListInteractionPanel(
                        interactionId = interaction.interactionId,
                        options = interaction.options,
                        isSubmitting = isSubmitting,
                        onSelect = onSelectInteractionOption,
                    )
                }

                InteractionVisualType.ITEM_REVIEW -> {
                    interaction.itemReview?.let {
                        ItemReviewInteractionContainer(
                            interactionId = interaction.interactionId,
                            state = it,
                            isSubmitting = isSubmitting,
                            onSubmitReview = onSubmitItemReview,
                        )
                    }
                }

                else -> {
                    H2Text(text = "Interaction type `${type}` is not supported in the current desktop slice.")
                }
            }
        }
    }
}

@Preview
@Composable
fun InteractionPanelPreview() {
    DesktopPreview {
        Column(
            verticalArrangement = Arrangement.spacedBy(Spacing.s6)
        ) {
            InteractionPanel(
                interaction = null,
                isSubmitting = false,
            )

            InteractionPanel(
                interaction = ActiveInteractionState(
                    interactionId = "",
                    stepId = "git_status",
                    stepName = "Check Git Status",
                    interactionType = InteractionVisualType.OPTION_LIST,
                    message = "This is a test",
                    options = listOf(
                        InteractionOptionState(
                            id = "option1",
                            label = "Option 1",
                            description = "This is option 1",
                            badges = listOf("Badge 1", "Badge 2"),
                        ),
                        InteractionOptionState(
                            id = "option2",
                            label = "Option 2",
                        )
                    ),
                ),
                isSubmitting = false,
            )
        }
    }
}
