package io.github.masorange.titan.desktop.ui.components.workflow

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.Card
import androidx.compose.material.ContentAlpha
import androidx.compose.material.LocalContentAlpha
import androidx.compose.material.LocalContentColor
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.state.SemanticContentItemState
import io.github.masorange.titan.desktop.theme.H3Text
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import io.github.masorange.titan.desktop.ui.LocalTheme
import io.github.masorange.titan.desktop.ui.components.progress.toDisplayColor
import com.halilibo.richtext.markdown.Markdown
import com.halilibo.richtext.ui.material.RichText

@Composable
fun MarkdownContentView(
    item: SemanticContentItemState,
    modifier: Modifier = Modifier,
) {
    val variantColor = item.variant.toDisplayColor()
    val contentColor = if (variantColor == Color.Unspecified) {
        LocalTheme.current.colors.palette.text.primary
    } else {
        variantColor
    }

    Card(
        modifier = modifier.fillMaxWidth(),
        backgroundColor = LocalTheme.current.colors.ui.previewBackground,
        elevation = 0.dp,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(Spacing.s6),
            verticalArrangement = Arrangement.spacedBy(Spacing.s4),
        ) {
            item.title?.let {
                H3Text(text = it, color = contentColor)
            }

            CompositionLocalProvider(
                LocalContentColor provides contentColor,
                LocalContentAlpha provides ContentAlpha.high,
            ) {
                RichText(modifier = Modifier.fillMaxWidth()) {
                    Markdown(content = item.content)
                }
            }
        }
    }
}
