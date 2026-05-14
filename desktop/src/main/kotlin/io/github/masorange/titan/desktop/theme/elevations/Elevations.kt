package es.masorange.freyja.core.theme.elevations

import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * Custom elevations to provide different values for each flavor.
 *
 * @param buttons Elevation values for buttons component.
 * @param chip Elevation values for the standard chip component.
 * @param filterChip Elevation values for the filter chip component.
 */
@Suppress("LongParameterList", "UseDataClass")
class Elevations(
    val buttons: Buttons,
    val card: Card,
    val chip: Chip,
    val filterChip: Chip
) {
    companion object {
        /**
         * Default elevation values. Only use for preview purposes.
         */
        internal val Default = Elevations(
            buttons = Buttons(
                default = 2.dp,
                pressed = 2.dp
            ),
            card = Card(
                default = 4.dp
            ),
            chip = Chip(
                default = 0.dp
            ),
            filterChip = Chip(
                default = 2.dp
            )
        )
    }
}

/**
 * The elevation values for the buttons component.
 *
 * @param default The elevation of the button in its normal state.
 * @param pressed The elevation of the button in its pressed state.
 */
data class Buttons(
    val default: Dp,
    val pressed: Dp
)

/**
 * The elevation values for the cards component.
 *
 * @param default The default elevation value.
 */
data class Card(
    val default: Dp
)

/**
 * The elevation values for the chip components.
 *
 * @param default The default elevation value.
 */
data class Chip(
    val default: Dp
)
