package io.github.masorange.titan.desktop.theme

import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import io.github.masorange.titan.desktop.ui.LocalTheme

/**
 * Custom typographies container to provide different text components.
 *
 * Each component is a wrapper around [TypographyText] with the corresponding style, which depends on the current [AppTheme].
 */

@Composable
fun H1Text(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.h1,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun H2Text(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.h2,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun H3Text(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.h3,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun H4Text(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.h4,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun H5Text(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.h5,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun H6Text(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.h6,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun Subtitle1RegularText(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.subtitle1.regular,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun Subtitle1StrongText(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.subtitle1.strong,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun Subtitle2RegularText(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.subtitle2.regular,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun Subtitle2StrongText(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.subtitle2.strong,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun Body1RegularText(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.body1.regular,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun Body1SecondaryText(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.body1.secondaryText,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun Body1StrongText(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null,
    textDecoration: TextDecoration? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.body1.strong,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase,
        textDecoration = textDecoration
    )
}

@Composable
fun Body2RegularText(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.body2.regular,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun Body2SecondaryText(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.body2.secondaryText,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun Body2StrongText(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.body2.strong,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun ButtonText(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.button,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun CaptionRegularText(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.caption.regular,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun CaptionStrongText(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.caption.strong,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}

@Composable
fun OverlineText(
    modifier: Modifier = Modifier,
    text: String,
    maxLines: Int = Int.MAX_VALUE,
    overflow: TextOverflow = TextOverflow.Clip,
    textAlign: TextAlign = TextAlign.Start,
    color: Color? = null,
    upperCase: Boolean? = null
) {
    TypographyText(
        modifier = modifier,
        text = text,
        style = LocalTheme.current.typography.typographyCatalog.overline,
        maxLines = maxLines,
        overflow = overflow,
        textAlign = textAlign,
        color = color,
        upperCase = upperCase
    )
}
//
//@Composable
//@UiPreview
//@FreyjaEntry(name = "Typography", category = FreyjaCatalogConstants.Categories.TYPOGRAPHY)
//@Suppress("LongMethod")
//fun AppTypographyComponentsPreview() {
//    UiPreviewLayout {
//        Column {
//            H1Text(text = "h1")
//            H2Text(text = "h2")
//            H3Text(text = "h3")
//            H4Text(text = "h4")
//            H5Text(text = "h5")
//            H6Text(text = "h6")
//            Subtitle1RegularText(text = "subtitle1Regular")
//            Subtitle1StrongText(text = "subtitle1Strong")
//            Subtitle2RegularText(text = "subtitle2Regular")
//            Subtitle2StrongText(text = "subtitle2Strong")
//            Body1RegularText(text = "body1Regular")
//            Body1SecondaryText(text = "body1SecondaryText")
//            Body1StrongText(text = "body1Strong")
//            Body2RegularText(text = "body2Regular")
//            Body2SecondaryText(text = "body2SecondaryText")
//            Body2StrongText(text = "body2Strong")
//            ButtonText(text = "button")
//            CaptionRegularText(text = "captionRegular")
//            CaptionStrongText(text = "captionStrong")
//            OverlineText(text = "overline")
//        }
//    }
//}
