package io.github.masorange.titan.desktop.theme

import androidx.compose.material.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.ParagraphStyle
import androidx.compose.ui.text.PlatformParagraphStyle
import androidx.compose.ui.text.PlatformSpanStyle
import androidx.compose.ui.text.PlatformTextStyle
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.style.LineHeightStyle
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import es.masorange.freyja.core.theme.typography.TypographyStyle
import es.masorange.freyja.core.theme.typography.withStyle

private val BaseTypographyTextStyle = TextStyle(
    platformStyle = PlatformTextStyle(
        spanStyle = PlatformSpanStyle(),
        paragraphStyle = PlatformParagraphStyle(),
    ),
    lineHeightStyle = LineHeightStyle(
        alignment = LineHeightStyle.Alignment.Center,
        trim = LineHeightStyle.Trim.None
    )
)

/**
 * Component wrapper that relies on [Text] to render a [AnnotatedString] with a custom [TypographyStyle].
 *
 * @param text the text to be displayed
 * @param modifier the [Modifier] to be applied to this layout node
 * @param textAlign the alignment of the text within the lines of the paragraph. See
 *   [TextStyle.textAlign].
 * @param maxLines An optional maximum number of lines for the text to span, wrapping if necessary.
 *   If the text exceeds the given number of lines, it will be truncated according to [overflow].
 * @param overflow how visual overflow should be handled.
 */
@Composable
internal fun TypographyText(
    text: AnnotatedString,
    modifier: Modifier = Modifier,
    textAlign: TextAlign = TextAlign.Start,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip
) {
    Text(
        text = text,
        style = BaseTypographyTextStyle,
        modifier = modifier,
        textAlign = textAlign,
        maxLines = maxLines,
        overflow = overflow
    )
}

/**
 * Component wrapper that relies on [Text] to render a [String] with a custom [TypographyStyle].
 *
 * @param text the text to be displayed
 * @param modifier the [Modifier] to be applied to this layout node
 * @param style the [TypographyStyle] to be applied to the text.
 * @param color the color of the text. Defaults to [style.color] if no color is provided.
 * @param upperCase whether the text should be displayed in uppercase. Defaults to [style.upperCase] if no uppercase value is provided.
 * @param textAlign the alignment of the text within the lines of the paragraph. See
 *   [TextStyle.textAlign].
 * @param maxLines An optional maximum number of lines for the text to span, wrapping if necessary.
 *   If the text exceeds the given number of lines, it will be truncated according to [overflow].
 * @param overflow how visual overflow should be handled.
 */
@Composable
internal fun TypographyText(
    text: String,
    modifier: Modifier = Modifier,
    style: TypographyStyle,
    color: Color? = null,
    upperCase: Boolean? = null,
    textAlign: TextAlign = TextAlign.Start,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textDecoration: TextDecoration? = null
) {
    val finalStyle = remember(style, color, upperCase, textDecoration) {
        style.copy(
            color = color ?: style.color,
            upperCase = upperCase ?: style.upperCase,
            textDecoration = textDecoration ?: style.textDecoration
        )
    }

    val annotatedText = remember(text, finalStyle) {
        buildAnnotatedString {
            withStyle(finalStyle) {
                append(if (finalStyle.upperCase) text.uppercase() else text)
            }
        }
    }

    TypographyText(
        text = annotatedText,
        modifier = modifier,
        textAlign = textAlign,
        maxLines = maxLines,
        overflow = overflow
    )
}
