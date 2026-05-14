package es.masorange.freyja.core.theme.shapes

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.unit.dp

/**
 * Custom shapes container to provide different values for each flavor.
 *
 * @param roundedCornerButton The style for the roundedCornerButtons.
 * @param roundedCornerFlag The style for the roundedCornerFlags.
 * @param roundedCornerCard The style for the roundedCornerCards.
 *
 */
@Suppress("LongParameterList", "UseDataClass")
class Shapes(
    val roundedCornerButton: RoundedCornerButton,
    val roundedCornerFlag: RoundedCornerShape,
    val roundedCornerCard: RoundedCornerShape
) {
    companion object {
        /**
         * Default shapes values. Only use for preview purposes.
         */
        internal val Default = Shapes(
            roundedCornerButton = RoundedCornerButton(
                large = RoundedCornerShape(24.dp),
                medium = RoundedCornerShape(20.dp),
                small = RoundedCornerShape(16.dp)
            ),
            roundedCornerFlag = RoundedCornerShape(4.dp),
            roundedCornerCard = RoundedCornerShape(4.dp)
        )
    }
}

/**
 * The shapes for the rounded corner buttons.
 *
 * @param large The shape for long rounded buttons.
 * @param medium The shape for medium rounded buttons.
 * @param small The shape for small rounded buttons.
 */
data class RoundedCornerButton(
    val large: RoundedCornerShape,
    val medium: RoundedCornerShape,
    val small: RoundedCornerShape
)
