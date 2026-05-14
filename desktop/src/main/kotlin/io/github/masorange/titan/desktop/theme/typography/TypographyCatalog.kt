package es.masorange.freyja.core.theme.typography

import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import io.github.masorange.titan.desktop.theme.colors.ColorPalette
import io.github.masorange.titan.desktop.theme.colors.ComponentColors

/**
 * Container for the typographies catalog and component typographies used in the app.
 *
 * @param typographyCatalog The typography catalog used for the app, containing various typography definitions.
 * @param components The typographies used for various components in the app.
 */
data class Typography(val typographyCatalog: TypographyCatalog, val components: ComponentTypographies) {
    companion object {
        internal val Default = Typography(
            TypographyCatalog.Default,
            ComponentTypographies.Default
        )
    }
}
/**
 * Custom typographies container to provide different values for each flavor.
 *
 * Each component is a wrapper around [TypographyStyle] with the corresponding style, which depends on the current [Theme].
 *
 * @param h1 The style for the H1 heading.
 * @param h2 The style for the H2 heading.
 * @param h3 The style for the H3 heading.
 * @param h4 The style for the H4 heading.
 * @param h5 The style for the H5 heading.
 * @param h6 The style for the H6 heading.
 * @param subtitle1 The style for the first subtitle.
 * @param subtitle2 The style for the second subtitle.
 * @param body1 The style for the first body text.
 * @param body2 The style for the second body text.
 * @param button The style for buttons.
 * @param caption The style for captions.
 * @param overline The style for overline text.
 */
@Suppress("LongParameterList", "UseDataClass")
class TypographyCatalog(
    val h1: TypographyStyle,
    val h2: TypographyStyle,
    val h3: TypographyStyle,
    val h4: TypographyStyle,
    val h5: TypographyStyle,
    val h6: TypographyStyle,
    val subtitle1: Subtitle1,
    val subtitle2: Subtitle2,
    val body1: Body1,
    val body2: Body2,
    val button: TypographyStyle,
    val caption: Caption,
    val overline: TypographyStyle
) {
    companion object {
        /**
         * Default typography. Only use for preview purposes.
         */
        internal val Default = TypographyCatalog(
            h1 = TypographyStyle(
                fontWeight = FontWeight.Bold,
                fontSize = 24.sp,
                lineHeight = 36.sp,
                letterSpacing = 0.sp,
                color = ColorPalette.Default.text.primary,
                upperCase = true
            ),
            h2 = TypographyStyle(
                fontWeight = FontWeight.Bold,
                fontSize = 22.sp,
                lineHeight = 28.sp,
                letterSpacing = 0.sp,
                color = ColorPalette.Default.text.primary,
                upperCase = true
            ),
            h3 = TypographyStyle(
                fontWeight = FontWeight.Bold,
                fontSize = 18.sp,
                lineHeight = 24.sp,
                letterSpacing = 0.sp,
                color = ColorPalette.Default.text.primary
            ),
            h4 = TypographyStyle(
                fontWeight = FontWeight.Medium,
                fontSize = 18.sp,
                lineHeight = 24.sp,
                letterSpacing = 0.sp,
                color = ColorPalette.Default.text.primary

            ),
            h5 = TypographyStyle(
                fontWeight = FontWeight.Bold,
                fontSize = 16.sp,
                lineHeight = 24.sp,
                letterSpacing = 0.sp,
                color = ColorPalette.Default.text.primary
            ),
            h6 = TypographyStyle(
                fontWeight = FontWeight.Bold,
                fontSize = 14.sp,
                lineHeight = 20.sp,
                letterSpacing = 0.sp,
                color = ColorPalette.Default.text.primary
            ),
            subtitle1 = Subtitle1(
                regular = TypographyStyle(
                    fontWeight = FontWeight.Normal,
                    fontSize = 20.sp,
                    lineHeight = 28.sp,
                    letterSpacing = 0.sp,
                    color = ColorPalette.Default.text.primary
                ),
                strong = TypographyStyle(
                    fontWeight = FontWeight.Bold,
                    fontSize = 20.sp,
                    lineHeight = 28.sp,
                    letterSpacing = 0.sp,
                    color = ColorPalette.Default.text.primary
                )
            ),
            subtitle2 = Subtitle2(
                regular = TypographyStyle(
                    fontWeight = FontWeight.Normal,
                    fontSize = 18.sp,
                    lineHeight = 24.sp,
                    letterSpacing = 0.sp,
                    color = ColorPalette.Default.text.primary
                ),
                strong = TypographyStyle(
                    fontWeight = FontWeight.Bold,
                    fontSize = 18.sp,
                    lineHeight = 24.sp,
                    letterSpacing = 0.sp,
                    color = ColorPalette.Default.text.primary
                )
            ),
            body1 = Body1(
                regular = TypographyStyle(
                    fontWeight = FontWeight.Normal,
                    fontSize = 16.sp,
                    lineHeight = 24.sp,
                    letterSpacing = 0.sp,
                    color = ColorPalette.Default.text.primary
                ),
                secondaryText = TypographyStyle(
                    fontWeight = FontWeight.Normal,
                    fontSize = 16.sp,
                    lineHeight = 24.sp,
                    letterSpacing = 0.sp,
                    color = ColorPalette.Default.text.secondary
                ),
                strong = TypographyStyle(
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp,
                    lineHeight = 24.sp,
                    letterSpacing = 0.sp,
                    color = ColorPalette.Default.text.primary
                )
            ),
            body2 = Body2(
                regular = TypographyStyle(
                    fontWeight = FontWeight.Normal,
                    fontSize = 14.sp,
                    lineHeight = 20.sp,
                    letterSpacing = 0.sp,
                    color = ColorPalette.Default.text.primary
                ),
                secondaryText = TypographyStyle(
                    fontWeight = FontWeight.Normal,
                    fontSize = 14.sp,
                    lineHeight = 20.sp,
                    letterSpacing = 0.sp,
                    color = ColorPalette.Default.text.secondary
                ),
                strong = TypographyStyle(
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp,
                    lineHeight = 20.sp,
                    letterSpacing = 0.sp,
                    color = ColorPalette.Default.text.primary
                )
            ),
            button = TypographyStyle(
                fontWeight = FontWeight.Bold,
                fontSize = 16.sp,
                lineHeight = 24.sp,
                letterSpacing = 0.sp,
                color = ColorPalette.Default.text.primary,
                upperCase = true
            ),
            caption = Caption(
                regular = TypographyStyle(
                    fontWeight = FontWeight.Normal,
                    fontSize = 12.sp,
                    lineHeight = 14.sp,
                    letterSpacing = 0.sp,
                    color = ColorPalette.Default.text.primary
                ),
                strong = TypographyStyle(
                    fontWeight = FontWeight.Bold,
                    fontSize = 12.sp,
                    lineHeight = 14.sp,
                    letterSpacing = 0.sp,
                    color = ColorPalette.Default.text.primary
                )
            ),
            overline = TypographyStyle(
                fontWeight = FontWeight.Medium,
                fontSize = 12.sp,
                lineHeight = 14.sp,
                letterSpacing = 0.sp,
                color = ColorPalette.Default.text.primary,
                upperCase = true
            )
        )
    }
}

/**
 * Custom components related typographies to provide different values for each flavor.
 *
 * Each component is a wrapper around [TypographyStyle] with the corresponding style, which depends on the current [Theme].
 *
 * @param typography The typography catalog used for the app, containing various typography definitions.
 * @param colors The color palette used for various components in the app, which also depends on the current [Theme].
 */
abstract class ComponentTypographies(val typography: TypographyCatalog, val colors: ComponentColors) {
    companion object {
        /**
         * Default components typography. Only use for preview purposes.
         */
        internal val Default = object : ComponentTypographies(typography = TypographyCatalog.Default, colors = ComponentColors.Default) {
            override val link: Link = Link(
                regular = TypographyStyle(
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp,
                    lineHeight = 24.sp,
                    letterSpacing = 0.sp,
                    color = colors.primaryLink.default
                ),
                small = TypographyStyle(
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp,
                    lineHeight = 20.sp,
                    letterSpacing = 0.sp,
                    color = colors.primaryLink.default
                )
            )
            override val stateTag: OrderTrackingStateTag = OrderTrackingStateTag(
                regular = TypographyStyle(
                    fontWeight = FontWeight.Medium,
                    fontSize = 14.sp,
                    lineHeight = 20.sp,
                    letterSpacing = 0.sp,
                    color = colors.palette.info.contrastText
                )
            )
            override val button: Button = Button(
                large = TypographyStyle(
                    fontWeight = FontWeight.Bold,
                    fontSize = 18.sp,
                    lineHeight = 24.sp,
                    letterSpacing = 0.sp,
                    color = ColorPalette.Default.text.primary,
                    upperCase = true
                ),
                medium = TypographyStyle(
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp,
                    lineHeight = 24.sp,
                    letterSpacing = 0.sp,
                    color = ColorPalette.Default.text.primary,
                    upperCase = true
                ),
                small = TypographyStyle(
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp,
                    lineHeight = 16.sp,
                    letterSpacing = 0.sp,
                    color = ColorPalette.Default.text.primary,
                    upperCase = true
                )
            )

            override val textField: TextField = TextField(
                active = TypographyStyle(
                    fontWeight = FontWeight.Normal,
                    fontSize = 16.sp,
                    lineHeight = 24.sp,
                    letterSpacing = 0.sp,
                    color = colors.textField.unfocusedText
                ),
                disable = TypographyStyle(
                    fontWeight = FontWeight.Normal,
                    fontSize = 16.sp,
                    lineHeight = 24.sp,
                    letterSpacing = 0.sp,
                    color = colors.textField.disabled
                ),
                helper = TypographyStyle(
                    fontWeight = FontWeight.Normal,
                    fontSize = 12.sp,
                    lineHeight = 16.sp,
                    letterSpacing = 0.sp,
                    color = colors.textField.unfocusedContainer
                ),
                error = TypographyStyle(
                    fontWeight = FontWeight.Normal,
                    fontSize = 12.sp,
                    lineHeight = 16.sp,
                    letterSpacing = 0.sp,
                    color = colors.textField.error
                )
            )
            override val filterChip: FilterChip = FilterChip(
                regular = TypographyStyle(
                    fontWeight = FontWeight.Normal,
                    fontSize = 12.sp,
                    lineHeight = 16.sp,
                    letterSpacing = 0.sp,
                    color = colors.palette.grey.g800
                )
            )

            override val tabItem: TabItem = TabItem(
                defaultActive = TypographyStyle(
                    fontWeight = FontWeight.Normal,
                    fontSize = 14.sp,
                    lineHeight = 16.sp,
                    letterSpacing = 0.sp,
                    color = colors.tabBar.tabItemActive
                ),
                defaultInactive = TypographyStyle(
                    fontWeight = FontWeight.Normal,
                    fontSize = 14.sp,
                    lineHeight = 16.sp,
                    letterSpacing = 0.sp,
                    color = colors.tabBar.tabItemInactive
                ),
                secondaryActive = TypographyStyle(
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp,
                    lineHeight = 16.sp,
                    letterSpacing = 0.sp,
                    color = colors.filledTabBar.tabItemActive
                ),
                secondaryInactive = TypographyStyle(
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp,
                    lineHeight = 16.sp,
                    letterSpacing = 0.sp,
                    color = colors.filledTabBar.tabItemInactive
                )
            )

            override val bottomBar = BottomBar(
                active = TypographyStyle(
                    fontWeight = FontWeight.Normal,
                    fontSize = 12.sp,
                    lineHeight = 16.sp,
                    letterSpacing = 4.sp,
                    color = colors.bottomBar.active
                ),
                inactive = TypographyStyle(
                    fontWeight = FontWeight.Normal,
                    fontSize = 12.sp,
                    lineHeight = 16.sp,
                    letterSpacing = 4.sp,
                    color = colors.bottomBar.inactive
                )
            )
        }
    }

    /**
     * The main typography used for the Link component.
     */
    abstract val link: Link
    /**
     * The main typography used for the State Tag component.
     */
    abstract val stateTag: OrderTrackingStateTag

    /**
     * The main typography used for the Button component.
     */
    abstract val button: Button

    /**
     * The main typography used for the TextField component.
     */
    abstract val textField: TextField

    /**
     * The main typography used for the FilterChip component.
     */
    abstract val filterChip: FilterChip

    /**
     * he main typography used for the TabItem component.
     */
    abstract val tabItem: TabItem

    /**
     * The main typography used for the BottomBar component.
     */
    abstract val bottomBar: BottomBar

    /**
     * Link component typography.
     */
    data class Link(val regular: TypographyStyle, val small: TypographyStyle)

    /**
     * Order Tracking Status Tag component typography.
     */
    data class OrderTrackingStateTag(val regular: TypographyStyle)

    /**
     * Button component typography.
     */
    data class Button(
        val large: TypographyStyle,
        val medium: TypographyStyle,
        val small: TypographyStyle
    )

    /**
     * TextField component typography.
     */
    data class TextField(
        val active: TypographyStyle,
        val disable: TypographyStyle,
        val helper: TypographyStyle,
        val error: TypographyStyle
    )

    /**
     * The main typography used for the FilterChip component.
     */
    data class FilterChip(val regular: TypographyStyle)

    /**
     * TabItem component typography.
     */
    data class TabItem(
        val defaultActive: TypographyStyle,
        val defaultInactive: TypographyStyle,
        val secondaryActive: TypographyStyle,
        val secondaryInactive: TypographyStyle
    )

    /**
     * BottomBar component typography.
     */
    data class BottomBar(
        val active: TypographyStyle,
        val inactive: TypographyStyle
    )
}

/**
 * The style for the first subtitle.
 *
 * @param regular The regular style for the subtitle.
 * @param strong The strong style for the subtitle.
 */
data class Subtitle1(
    val regular: TypographyStyle,
    val strong: TypographyStyle
)

/**
 * The style for the second subtitle.
 *
 * @param regular The regular style for the subtitle.
 * @param strong The strong style for the subtitle.
 */
data class Subtitle2(
    val regular: TypographyStyle,
    val strong: TypographyStyle
)

/**
 * The style for the first body text.
 *
 * @param regular The regular style for the body text.
 * @param secondaryText The secondary text style for the body text.
 * @param strong The strong style for the body text.
 */
data class Body1(
    val regular: TypographyStyle,
    val secondaryText: TypographyStyle,
    val strong: TypographyStyle
)

/**
 * The style for the second body text.
 *
 * @param regular The regular style for the body text.
 * @param secondaryText The secondary text style for the body text.
 * @param strong The strong style for the body text.
 */
data class Body2(
    val regular: TypographyStyle,
    val secondaryText: TypographyStyle,
    val strong: TypographyStyle
)

/**
 * The style for captions.
 *
 * @param regular The regular style for the caption.
 * @param strong The strong style for the caption.
 */
data class Caption(
    val regular: TypographyStyle,
    val strong: TypographyStyle
)
