package io.github.masorange.titan.desktop.theme

import es.masorange.freyja.core.theme.elevations.Elevations
import es.masorange.freyja.core.theme.shapes.Shapes
import es.masorange.freyja.core.theme.sizes.Sizes
import es.masorange.freyja.core.theme.typography.Typography
import io.github.masorange.titan.desktop.theme.colors.Colors
import io.github.masorange.titan.desktop.theme.spacings.Spacing

/**
 * Represents the theme of the app, including color palette and typography.
 */
data class Theme(
    val colors: Colors,
    val typography: Typography,
    val spacings: Spacing = Spacing,
    val sizes: Sizes,
    val shapes: Shapes,
    val elevations: Elevations
) {
    companion object {
        internal val Default = Theme(
            colors = Colors.Default,
            typography = Typography.Default,
            spacings = Spacing,
            sizes = Sizes.Default,
            shapes = Shapes.Default,
            elevations = Elevations.Default
        )
    }
}
