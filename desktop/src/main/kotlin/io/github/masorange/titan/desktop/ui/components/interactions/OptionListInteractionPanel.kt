package io.github.masorange.titan.desktop.ui.components.interactions

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.ButtonDefaults
import androidx.compose.material.Card
import androidx.compose.material.MaterialTheme
import androidx.compose.material.OutlinedButton
import androidx.compose.material.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.InteractionOptionState
import io.github.masorange.titan.desktop.theme.Body1StrongText
import io.github.masorange.titan.desktop.theme.CaptionRegularText
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun OptionListInteractionPanel(
    interactionId: String,
    options: List<InteractionOptionState>,
    isSubmitting: Boolean,
    onSelect: (String, String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(Spacing.s5),
    ) {
        options.forEach { option ->
            OptionListInteractionItem(
                modifier = Modifier.fillMaxWidth(),
                interactionId = interactionId,
                option = option,
                isSubmitting = isSubmitting,
                onSelect = onSelect,
            )
        }
    }
}

@Composable
private fun OptionListInteractionItem(
    modifier: Modifier = Modifier,
    interactionId: String,
    option: InteractionOptionState,
    isSubmitting: Boolean,
    onSelect: (String, String) -> Unit,
) {
    OutlinedButton(
        modifier = modifier.fillMaxWidth(),
        onClick = { onSelect(interactionId, option.id) },
        enabled = !isSubmitting,
        shape = RoundedCornerShape(Spacing.s4),
        colors = ButtonDefaults.outlinedButtonColors(
            backgroundColor = MaterialTheme.colors.surface,
            contentColor = MaterialTheme.colors.onSurface,
        ),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(Spacing.s6),
            verticalArrangement = Arrangement.spacedBy(Spacing.s4),
        ) {
            Body1StrongText(
                text = option.label,
            )
            option.description?.let {
                CaptionRegularText(
                    text = it
                )
            }
            if (option.badges.isNotEmpty()) {
                Row(horizontalArrangement = Arrangement.spacedBy(Spacing.s3)) {
                    option.badges.forEach { badge ->
                        Card(elevation = 0.dp) {
                            Text(
                                text = badge,
                                modifier = Modifier.padding(horizontal = Spacing.s4, vertical = Spacing.s2),
                                style = MaterialTheme.typography.caption,
                                fontWeight = FontWeight.Medium,
                            )
                        }
                    }
                }
            }
        }
    }
}

@Preview
@Composable
private fun OptionListInteractionPanelPreview() {
    MaterialTheme {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color.White)
                .padding(Spacing.s6)
        ) {
            OptionListInteractionPanel(
                interactionId = "select-cli:select-cli",
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
                isSubmitting = false,
                onSelect = { _, _ -> },
            )
        }
    }
}
