package io.github.masorange.titan.desktop.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.ProvidableCompositionLocal
import androidx.compose.runtime.compositionLocalOf
import io.github.masorange.titan.desktop.theme.Theme

/**
 * [CompositionLocal] that provides the app theme and allows its use in [Composable]s.
 */
val LocalTheme: ProvidableCompositionLocal<Theme> =
    compositionLocalOf { Theme.Default }

/**
 * [CompositionLocal] that provides an optional theme variant identifier.
 *
 * Brands can use this to provide different color schemes or theme configurations
 * based on runtime values (e.g., user preferences, business units, regions, etc.).
 *
 * The variant identifier is a generic string that each brand can interpret as needed.
 * Brands that don't support multiple variants can simply ignore this value.
 *
 * Example usage:
 * ```kotlin
 * // In the app:
 * CompositionLocalProvider(LocalThemeVariant provides "premium") {
 *     // ...
 * }
 *
 * // In the brand theme module:
 * val variant = LocalThemeVariant.current
 * val palette = when (variant) {
 *     "premium" -> premiumColorPalette
 *     else -> defaultColorPalette
 * }
 * ```
 */
val LocalThemeVariant: ProvidableCompositionLocal<String?> =
    compositionLocalOf { null }

/**
 * Provides the app theme to the [content] [Composable].
 *
 * @param theme The [Theme] to be provided.
 * @param content The [Composable] content that will use the provided theme.
 */
@Composable
fun withLocalTheme(theme: Theme, content: @Composable () -> Unit) {
    CompositionLocalProvider(LocalTheme provides theme) {
        content()
    }
}
