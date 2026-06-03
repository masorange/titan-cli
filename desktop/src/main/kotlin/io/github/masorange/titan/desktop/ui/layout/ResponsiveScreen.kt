package io.github.masorange.titan.desktop.ui.layout

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import io.github.masorange.titan.desktop.theme.spacings.Spacing

enum class ScreenWidthClass {
    Compact,
    Medium,
    Expanded,
}

enum class ContainerSize {
    Narrow,
    Default,
    Wide,
    Full,
}

data class ResponsiveScreenSpec(
    val widthClass: ScreenWidthClass,
    val containerSize: ContainerSize,
    val contentMaxWidth: Dp,
    val horizontalPadding: Dp,
    val verticalPadding: Dp,
    val sectionSpacing: Dp,
)

@Composable
fun ResponsiveScreen(
    modifier: Modifier = Modifier,
    containerSize: ContainerSize = ContainerSize.Default,
    content: @Composable ColumnScope.(ResponsiveScreenSpec) -> Unit,
) {
    BoxWithConstraints(modifier = modifier.fillMaxSize()) {
        val spec = responsiveScreenSpec(maxWidth, containerSize)

        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(
                    horizontal = spec.horizontalPadding,
                    vertical = spec.verticalPadding,
                ),
            contentAlignment = Alignment.TopCenter,
        ) {
            Column(
                modifier = Modifier
                    .widthIn(max = spec.contentMaxWidth)
                    .fillMaxWidth()
                    .fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(spec.sectionSpacing),
            ) {
                content(spec)
            }
        }
    }
}

private fun responsiveScreenSpec(
    maxWidth: Dp,
    containerSize: ContainerSize,
): ResponsiveScreenSpec = when {
    maxWidth < 960.dp -> ResponsiveScreenSpec(
        widthClass = ScreenWidthClass.Compact,
        containerSize = containerSize,
        contentMaxWidth = contentMaxWidthFor(containerSize, ScreenWidthClass.Compact),
        horizontalPadding = Spacing.s5,
        verticalPadding = Spacing.s5,
        sectionSpacing = Spacing.s6,
    )

    maxWidth < 1440.dp -> ResponsiveScreenSpec(
        widthClass = ScreenWidthClass.Medium,
        containerSize = containerSize,
        contentMaxWidth = contentMaxWidthFor(containerSize, ScreenWidthClass.Medium),
        horizontalPadding = Spacing.s11,
        verticalPadding = Spacing.s6,
        sectionSpacing = Spacing.s6,
    )

    else -> ResponsiveScreenSpec(
        widthClass = ScreenWidthClass.Expanded,
        containerSize = containerSize,
        contentMaxWidth = contentMaxWidthFor(containerSize, ScreenWidthClass.Expanded),
        horizontalPadding = Spacing.s12,
        verticalPadding = Spacing.s7,
        sectionSpacing = Spacing.s7,
    )
}

private fun contentMaxWidthFor(
    containerSize: ContainerSize,
    widthClass: ScreenWidthClass,
): Dp = when (containerSize) {
    ContainerSize.Narrow -> when (widthClass) {
        ScreenWidthClass.Compact -> Dp.Unspecified
        ScreenWidthClass.Medium -> 760.dp
        ScreenWidthClass.Expanded -> 760.dp
    }

    ContainerSize.Default -> when (widthClass) {
        ScreenWidthClass.Compact -> Dp.Unspecified
        ScreenWidthClass.Medium -> 840.dp
        ScreenWidthClass.Expanded -> 840.dp
    }

    ContainerSize.Wide -> when (widthClass) {
        ScreenWidthClass.Compact -> Dp.Unspecified
        ScreenWidthClass.Medium -> 1040.dp
        ScreenWidthClass.Expanded -> 1040.dp
    }

    ContainerSize.Full -> Dp.Unspecified
}
