package es.masorange.freyja.core.theme.typography

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.*
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.TextUnit

/**
 * Typography style configuration for text elements.
 *
 * This class wraps several text styling properties inherited from [TextStyle] and extends them with other properties like [upperCase].
 *
 * @param fontFamily The font family to be used when rendering the text.
 * @param fontWeight The typeface thickness to use when painting the text (e.g., bold).
 * @param fontSize The size of glyphs to use when painting the text. This may be [TextUnit.Unspecified] for inheriting
 *   from another [TextStyle].
 * @param lineHeight Line height for the [Paragraph] in [TextUnit] unit, e.g. SP or EM.
 * @param letterSpacing The amount of space to add between each letter.
 * @param color The text color.
 * @param upperCase If true, the text will be rendered in uppercase.
 * @param textDecoration The decorations to be applied to the text (e.g., underline, line-through).
 *
 * @see AnnotatedString
 * @see SpanStyle
 * @see ParagraphStyle
 */
data class TypographyStyle(
    val fontFamily: FontFamily? = null,
    val fontWeight: FontWeight? = null,
    val fontSize: TextUnit = TextUnit.Unspecified,
    val lineHeight: TextUnit = TextUnit.Unspecified,
    val letterSpacing: TextUnit = TextUnit.Unspecified,
    val textDecoration: TextDecoration = TextDecoration.None,
    val color: Color = Color.Unspecified,
    val upperCase: Boolean = false
) {
    /**
     * The [TextStyle] representation of this typography style.
     */
    val textStyle: TextStyle by lazy {
        TextStyle(
            color = color,
            fontSize = fontSize,
            fontWeight = fontWeight,
            fontFamily = fontFamily,
            lineHeight = lineHeight,
            textDecoration = textDecoration,
            letterSpacing = letterSpacing
        )
    }

    /**
     * The [SpanStyle] representation of this typography style.
     */
    val spanStyle: SpanStyle by lazy {

        SpanStyle(
            color = color,
            fontSize = fontSize,
            fontWeight = fontWeight,
            fontFamily = fontFamily,
            textDecoration = textDecoration,
            letterSpacing = letterSpacing
        )
    }

    /**
     * The [ParagraphStyle] representation of this typography style.
     */
    val paragraphStyle: ParagraphStyle by lazy {

        ParagraphStyle(
            lineHeight = lineHeight,
            textIndent = null
        )
    }
}

/**
 * Pushes style to the AnnotatedString.Builder, executes block and then pops the style.
 */
inline fun <R : Any> AnnotatedString.Builder.withStyle(style: TypographyStyle, crossinline block: AnnotatedString.Builder.() -> R): R {
    return withStyle(style.paragraphStyle) {
        withStyle(style.spanStyle) {
            block(this)
        }
    }
}
