package io.github.masorange.titan.desktop.ui.components.workflow

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.Card
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.theme.H3Text
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import io.github.masorange.titan.desktop.ui.DesktopPreview
import io.github.masorange.titan.desktop.ui.LocalTheme
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun WorkflowSectionCard(
    modifier: Modifier = Modifier,
    section: String,
    content: @Composable () -> Unit
) {
    val colors = LocalTheme.current.colors.ui
    Card(
        modifier = modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = colors.sectionBorder,
                shape = RoundedCornerShape(16.dp),
            ),
        shape = RoundedCornerShape(16.dp),
        elevation = 4.dp,
        backgroundColor = colors.cardBackground,
    ) {
        Column(
            modifier = Modifier.fillMaxWidth()
        ) {
            Header(title = section)
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(Spacing.s4),
            ) {
                content()
            }
        }
    }
}

@Composable
private fun Header(modifier: Modifier = Modifier, title: String) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(LocalTheme.current.colors.ui.sectionHeaderBackground)
            .padding(Spacing.s6),
    ) {
        H3Text(text = title)
    }
}

@Preview
@Composable
fun WorkflowSectionCard() {
    DesktopPreview {
        WorkflowSectionCard(
            section = "Validate",
        ) {
            Column(
                modifier = Modifier.height(200.dp),
            ) {

            }
        }
    }
}
