package io.github.masorange.titan.desktop.ui.components.content

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.Card
import androidx.compose.material.MaterialTheme
import androidx.compose.material.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.ContentBlockState
import io.github.masorange.titan.desktop.state.ContentBlockVisualType
import io.github.masorange.titan.desktop.state.OutputItemState
import io.github.masorange.titan.desktop.state.OutputVisualVariant
import io.github.masorange.titan.desktop.state.OutputVisualFormat
import io.github.masorange.titan.desktop.theme.H4Text
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import io.github.masorange.titan.desktop.ui.components.diff.DiffOutputView
import io.github.masorange.titan.desktop.ui.components.structuredsummary.StructuredSummaryOutputView

@Composable
fun ContentBlockView(
    block: ContentBlockState,
    modifier: Modifier = Modifier,
) {
    when (block.type) {
        ContentBlockVisualType.TEXT -> TextContentBlockView(block = block, modifier = modifier)
        ContentBlockVisualType.MARKDOWN -> MarkdownContentBlockView(block = block, modifier = modifier)
        ContentBlockVisualType.DIFF -> DiffContentBlockView(block = block, modifier = modifier)
        ContentBlockVisualType.STRUCTURED_SUMMARY -> StructuredSummaryContentBlockView(block = block, modifier = modifier)
        ContentBlockVisualType.UNKNOWN -> FallbackContentBlockView(block = block, modifier = modifier)
    }
}

@Composable
private fun TextContentBlockView(block: ContentBlockState, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(Spacing.s3),
    ) {
        block.title?.let { H4Text(text = it) }
        Text(
            text = block.content,
            style = MaterialTheme.typography.body2,
            color = block.variant.toDisplayColor(),
        )
    }
}

@Composable
private fun MarkdownContentBlockView(block: ContentBlockState, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(Spacing.s3),
    ) {
        block.title?.let { H4Text(text = it) }
        Text(
            text = block.content,
            style = MaterialTheme.typography.body2,
            color = block.variant.toDisplayColor(),
        )
    }
}

@Composable
private fun DiffContentBlockView(block: ContentBlockState, modifier: Modifier = Modifier) {
    DiffOutputView(
        item = block.toOutputItemState(OutputVisualFormat.DIFF),
        modifier = modifier,
    )
}

@Composable
private fun StructuredSummaryContentBlockView(block: ContentBlockState, modifier: Modifier = Modifier) {
    Column(modifier = modifier.fillMaxWidth()) {
        StructuredSummaryOutputView(item = block.toOutputItemState(OutputVisualFormat.STRUCTURED_SUMMARY))
    }
}

@Composable
private fun FallbackContentBlockView(block: ContentBlockState, modifier: Modifier = Modifier) {
    Card(modifier = modifier.fillMaxWidth(), elevation = 0.dp) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(Spacing.s4),
            verticalArrangement = Arrangement.spacedBy(Spacing.s3),
        ) {
            H4Text(text = block.title ?: "Unsupported block")
            Text(
                text = "Type: ${block.type.wireValue}",
                style = MaterialTheme.typography.caption,
            )
            Text(
                text = block.content,
                style = MaterialTheme.typography.body2,
                fontFamily = FontFamily.Monospace,
            )
        }
    }
}

private fun ContentBlockState.toOutputItemState(format: OutputVisualFormat): OutputItemState = OutputItemState(
    sequence = 0,
    format = format,
    variant = variant,
    title = title,
    content = content,
    metadata = metadata,
)

@Composable
private fun OutputVisualVariant.toDisplayColor(): Color = when (this) {
    OutputVisualVariant.DEFAULT,
    OutputVisualVariant.UNKNOWN -> MaterialTheme.colors.onSurface
    OutputVisualVariant.SUCCESS -> Color(0xFF1F7A1F)
    OutputVisualVariant.MUTED -> MaterialTheme.colors.onSurface.copy(alpha = 0.6f)
    OutputVisualVariant.WARNING -> Color(0xFF9A6700)
    OutputVisualVariant.ERROR -> Color(0xFFB42318)
}
