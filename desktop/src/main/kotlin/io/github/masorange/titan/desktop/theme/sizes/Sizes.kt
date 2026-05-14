package es.masorange.freyja.core.theme.sizes

import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * Custom sizes container to provide different values for each flavor.
 *
 * @param linearProgressIndicator The style for the linearProgressIndicator.
 */
@Suppress("LongParameterList", "UseDataClass")
class Sizes(
    val linearProgressIndicator: LinearProgressIndicator
) {
    companion object {
        /**
         * Default sizes values. Only use for preview purposes.
         */
        internal val Default = Sizes(
            linearProgressIndicator = LinearProgressIndicator(
                height = 16.dp
            )
        )
    }
}

/**
 * The size for linear progress indicator.
 *
 * @param height The height for linear progress indicator
 */
data class LinearProgressIndicator(
    val height: Dp
)
