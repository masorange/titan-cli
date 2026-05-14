package io.github.masorange.titan.desktop.theme.colors

import androidx.compose.ui.graphics.Color

/**
 * Container for the color palette and component colors used in the app.
 *
 * @param palette The color palette used for the app, containing various color definitions.
 * @param components The colors used for various components in the app.
 */
data class Colors(val palette: ColorPalette, val components: ComponentColors) {
    companion object {
        internal val Default = Colors(
            palette = ColorPalette.Default,
            components = ComponentColors.Default
        )
    }
}

/**
 * Description of the color palette used in the apps.
 *
 * @param common Common colors used across the app, such as black and white.
 * @param primary Primary color used for main highlights.
 * @param secondary Secondary color used for secondary highlights.
 * @param tertiary Tertiary color used for additional highlights.
 * @param error Color used to indicate errors or critical issues.
 * @param warning Color used to indicate warnings or important notices.
 * @param info Color used to indicate informational messages.
 * @param success Color used to indicate successful actions or states.
 * @param link Color used for links and clickable text.
 * @param primaryAction Color used for primary actions, like buttons.
 * @param grey Shades of grey used for various UI elements.
 * @param text Colors used for text elements, including primary, secondary, and tertiary text.
 * @param background Colors used for different background elements, such as default, page, and section backgrounds.
 *
 * @sample ColorPalettePreview
 */
@Suppress("LongParameterList", "UseDataClass")
data class ColorPalette(
    val common: Common,
    val primary: Primary,
    val secondary: Secondary,
    val tertiary: Tertiary,
    val error: Error,
    val warning: Warning,
    val info: Info,
    val success: Success,
    val link: Link,
    val primaryAction: PrimaryAction,
    val grey: Grey,
    val text: Text,
    val background: Background
) {
    companion object {
        /**
         * Default color palette. Only use for preview purposes.
         */
        internal val Default = ColorPalette(
            common = Common(
                black = Color(0xFF000000),
                white = Color(0xFFFFFFFF),
                transparent = Color(0x00000000)
            ),
            primary = Primary(
                main = Color(0xFFAE3F97),
                light = Color(0xFFBD61A9),
                dark = Color(0xFF82107B),
                contrastText = Color(0xFFFFFFFF)
            ),
            secondary = Secondary(
                main = Color(0xFF613085),
                light = Color(0xFF8E409F),
                dark = Color(0xFF472772),
                contrastText = Color(0xFFFFFFFF)
            ),
            tertiary = Tertiary(
                main = Color(0xFF00A9CE),
                light = Color(0xFF81DBF6),
                dark = Color(0xFF35348A),
                contrastText = Color(0xFFFFFFFF)
            ),
            error = Error(
                main = Color(0xFFD0021B),
                light = Color(0xFFFF5144),
                dark = Color(0xFF960000),
                contrastText = Color(0xFFFFFFFF)
            ),
            warning = Warning(
                main = Color(0xFFFF9800),
                light = Color(0xFFFFB84D),
                dark = Color(0xFFEF6D00),
                contrastText = Color(0xFF000000)
            ),
            info = Info(
                main = Color(0xFF327DF5),
                light = Color(0xFF78ABFB),
                dark = Color(0xFF0049D8),
                contrastText = Color(0xFFFFFFFF)
            ),
            success = Success(
                main = Color(0xFF3EA200),
                light = Color(0xFF7FCF47),
                dark = Color(0xFF008E46),
                contrastText = Color(0xFFFFFFFF)
            ),
            link = Link(
                main = Color(0xFF1467EB),
                light = Color(0xFF6994FF),
                dark = Color(0xFF003EB7),
                contrastText = Color(0xFFFFFFFF)
            ),
            primaryAction = PrimaryAction(
                main = Color(0xFF3EA200),
                light = Color(0xFF7FCF47),
                dark = Color(0xFF008E46),
                contrastText = Color(0xFFFFFFFF)
            ),
            grey = Grey(
                g50 = Color(0xFFF6F6F6),
                g100 = Color(0xFFECECEC),
                g200 = Color(0xFFCECECE),
                g300 = Color(0xFFB3B3B3),
                g400 = Color(0xFF9B9B9B),
                g500 = Color(0xFF767676),
                g600 = Color(0xFF606060),
                g700 = Color(0xFF444444),
                g800 = Color(0xFF2E2E2E),
                g900 = Color(0xFF171717)
            ),
            text = Text(
                primary = Color(0xFF2E2E2E),
                secondary = Color(0xFF444444),
                tertiary = Color(0xFFCECECE)
            ),
            background = Background(
                default = Color(0xFFFFFFFF),
                pageColor = Color(0xFFF6F6F6),
                mainColor = Color(0xFFAE3F97),
                primary = Color(0xFFF4E4F0),
                secondary = Color(0xFFF1E6F3),
                tertiary = Color(0xFFE1F6FD),
                error = Color(0xFFFFDFDD),
                warning = Color(0xFFFFF3E0),
                info = Color(0xFFDDEAFE),
                success = Color(0xFFEEFAE6)
            )
        )
    }
}

/**
 * Colors used for various components in the app.
 *
 * @sample ComponentColorsPalettePreview
 */
abstract class ComponentColors(val palette: ColorPalette) {
    companion object {
        /**
         * Default components palette. Only use for preview purposes.
         */
        internal val Default = object : ComponentColors(ColorPalette.Default) {
            override val primaryLink: PrimaryLink = PrimaryLink(
                default = palette.link.main,
                hover = palette.link.main,
                active = palette.link.dark
            )
            override val circularProgressIndicator:  CircularProgressIndicator = CircularProgressIndicator(
                background = Color(0xFFe0e0e0),
                shadow = Color(0x19000000),
                normalStart = Color(0xFFb4ec51),
                normalEnd = Color(0xFF3ea200),
                disabled = Color(0xFFe0e0e0),
                warningStart = Color(0xFFff5244),
                warningMiddle = Color(0xFFe6282f),
                warningEnd = Color(0xFFd0021b)
            )
            override val linearProgressIndicator:  LinearProgressIndicator = LinearProgressIndicator(
                background = Color(0xFFececec),
                normal = Color(0xFF74d443),
                warning = Color(0xFFd0021b),
                disabled = Color(0xFFececec)
            )
            override val primaryButton: PrimaryButton = PrimaryButton(
                bgColorEnabled = palette.primaryAction.main,
                bgColorFocused = palette.primaryAction.main,
                bgColorHover = palette.primaryAction.dark,
                bgColorPressed = palette.primaryAction.light,
                bgColorDisabled = palette.grey.g200,
                textEnabled = palette.primaryAction.contrastText,
                textFocused = palette.primaryAction.contrastText,
                textHover = palette.primaryAction.contrastText,
                textPressed = palette.primaryAction.contrastText,
                textDisabled = palette.grey.g500,
                borderFocused = palette.primaryAction.dark
            )
            override val secondaryButton: SecondaryButton = SecondaryButton(
                bgColorEnabled = palette.common.white,
                bgColorFocused = palette.common.white,
                bgColorHover = palette.common.white,
                bgColorPressed = palette.grey.g50,
                bgColorDisabled = palette.common.white,
                borderEnabled = palette.grey.g800,
                borderFocused = palette.grey.g800,
                borderHover = palette.grey.g900,
                borderPressed = palette.grey.g900,
                borderDisabled = palette.grey.g200,
                textEnabled = palette.grey.g800,
                textFocused = palette.grey.g800,
                textHover = palette.grey.g900,
                textPressed = palette.grey.g900,
                textDisabled = palette.grey.g300
            )
            override val alertButton: AlertButton = AlertButton(
                bgColorEnabled = palette.common.white,
                bgColorFocused = palette.common.white,
                bgColorHover = palette.common.white,
                bgColorPressed = palette.background.error,
                bgColorDisabled = palette.common.white,
                borderEnabled = palette.error.main,
                borderFocused = palette.error.main,
                borderHover = palette.error.dark,
                borderPressed = palette.error.dark,
                borderDisabled = palette.grey.g200,
                textEnabled = palette.error.main,
                textFocused = palette.error.main,
                textHover = palette.error.dark,
                textPressed = palette.error.dark,
                textDisabled = palette.grey.g300
            )
            override val textButton: TextButton = TextButton(
                bgColorPressed = palette.background.info,
                bgColorHover = palette.common.transparent,
                textEnabled = palette.link.main,
                textFocused = palette.link.light,
                textHover = palette.link.dark,
                textPressed = palette.link.dark,
                textDisabled = palette.grey.g300
            )
            override val snackbar: Snackbar = Snackbar(
                bgColor = palette.grey.g900,
                text = palette.common.white,
                button = palette.link.light
            )
            override val textField: TextField = TextField(
                focused = palette.primary.main,
                unfocusedContainer = palette.grey.g500,
                unfocusedText = palette.common.black,
                disabled = palette.grey.g800,
                error = palette.error.main
            )
            override val forms: Forms = Forms(
                controlActive = palette.link.main,
                bgControlActive = palette.background.info,
                textfieldActive = palette.link.main,
                textfieldInactive = palette.grey.g500,
                textfieldDisabled = palette.grey.g200
            )
            override val selectors: Selectors = Selectors(
                selected = palette.primaryAction.main,
                checkmark = palette.common.white
            )
            override val numberRadioButton: NumberRadioButton = NumberRadioButton(
                background = palette.common.white,
                borderSelected = palette.primaryAction.main,
                borderUnselected = palette.grey.g300,
                textSelected = palette.text.primary,
                textEnabled = palette.text.secondary,
                textDisabled = palette.text.tertiary
            )
            override val switch: Switch = Switch(
                checkedThumbColor = palette.primaryAction.contrastText,
                checkedTrackColor = palette.primaryAction.main,
                uncheckedThumbColor = palette.grey.g300,
                uncheckedTrackColor = palette.grey.g100,
                uncheckedBorderColor = palette.grey.g300
            )
            override val chip: Chip = Chip(
                bgColorUnselected = palette.common.white,
                bgColorSelected = palette.primary.main,
                borderUnselected = palette.common.black,
                borderSelected = palette.primary.contrastText,
                textUnselected = palette.common.black,
                textSelected = palette.primary.contrastText
            )
            override val filterChip: Chip = Chip(
                bgColorUnselected = palette.background.default,
                bgColorSelected = palette.background.primary,
                borderUnselected = palette.grey.g500,
                borderSelected = palette.secondary.main,
                textUnselected = palette.grey.g500,
                textSelected = palette.grey.g800
            )
            override val tabBar: TabBar = TabBar(
                indicator = palette.primary.main,
                content = palette.background.default,
                container = palette.background.default,
                tabItemActive = palette.primary.main,
                tabItemInactive = palette.primary.main
            )
            override val filledTabBar: FilledTabBar = FilledTabBar(
                indicator = palette.common.white,
                content = palette.background.default,
                container = palette.primary.main,
                tabItemActive = palette.common.white,
                tabItemInactive = palette.grey.g50
            )
            override val card: Card = Card(
                background = palette.background.default,
                border = palette.grey.g300,
                shadow = palette.common.black
            )
            override val bottomBar: BottomBar = BottomBar(
                active = palette.primary.main,
                inactive = palette.grey.g500,
                background = palette.common.white,
                selectedIcon = palette.common.white,
                selectedBubble = palette.primary.main
            )
        }
    }

     /**
     * The main color used for the Primary Link component.
     */
    abstract val primaryLink: PrimaryLink
     /**
     * The main color used for the Circular Progress Indicator component.
     */
    abstract val circularProgressIndicator: CircularProgressIndicator

    /**
     * The main color used for the Linear Progress Indicator component.
     */
    abstract val linearProgressIndicator: LinearProgressIndicator
    /**
     * The component colors palette [PrimaryButton] used for the Primary Button.
     */
    abstract val primaryButton: PrimaryButton

    /**
     * The component colors palette [SecondaryButton] used for the Secondary Button.
     */
    abstract val secondaryButton: SecondaryButton

    /**
     * The component colors palette [AlertButton] used for the Alert Button.
     */
    abstract val alertButton: AlertButton

    /**
     * The component colors palette [TextButton] used for the Text Button.
     */
    abstract val textButton: TextButton

    /**
     * The component colors palette [Snackbar] used for the snackbar.
     */
    abstract val snackbar: Snackbar

    /**
     * The colors used for the TextField component.
     */
    abstract val textField: TextField

    /**
     * The component colors palette [Forms] used for forms.
     */
    abstract val forms: Forms

    /**
     * The component colors palette [Selectors] used for checkbox, radio button...
     */
    abstract val selectors: Selectors

    /**
     * The component colors palette [NumberRadioButton] used for number radio button.
     */
    abstract val numberRadioButton: NumberRadioButton

    /**
     * The component colors palette [Switch] used for switch component.
     */
    abstract val switch: Switch

    /**
     * The component colors palette [Chip] used for chips.
     */
    abstract val chip: Chip

    /**
     * The component colors palette [Chip] used for filter chips.
     */
    abstract val filterChip: Chip

    /**
     * The component colors palette [TabBar] used for top bar.
     */
    abstract val tabBar: TabBar

    /**
     * The component colors palette [FilledTabBar] used for top bar.
     */
    abstract val filledTabBar: FilledTabBar

    /**
     * The component colors palette [Card] used for card.
     */
    abstract val card: Card

    /**
     * The component colors palette [BottomBar] used for bottom bar.
     */
    abstract val bottomBar: BottomBar

    /**
     * PrimaryLink component colors for different states.
     *
     * @param default The default color of the primary link.
     * @param hover The color of the primary link when hovered.
     * @param active The color of the primary link when active or pressed.
     */
    data class PrimaryLink(
        val default: Color,
        val hover: Color,
        val active: Color
    )

    /**
     * Circular Progress Indicator component color.
     */
    data class CircularProgressIndicator(
        val background: Color,
        val shadow: Color,
        val normalStart: Color,
        val normalEnd: Color,
        val disabled: Color,
        val warningStart: Color,
        val warningMiddle: Color,
        val warningEnd: Color
    )
    /**
     * Linear Progress Indicator component color.
     */
    data class LinearProgressIndicator(
        val background: Color,
        val normal: Color,
        val warning: Color,
        val disabled: Color
    )
    /**
     * PrimaryButton component colors.
     */
    data class PrimaryButton(
        val bgColorEnabled: Color,
        val bgColorFocused: Color,
        val bgColorHover: Color,
        val bgColorPressed: Color,
        val bgColorDisabled: Color,
        val textEnabled: Color,
        val textFocused: Color,
        val textHover: Color,
        val textPressed: Color,
        val textDisabled: Color,
        val borderFocused: Color
    )

    /**
     * SecondaryButton component colors.
     */
    data class SecondaryButton(
        val bgColorEnabled: Color,
        val bgColorFocused: Color,
        val bgColorHover: Color,
        val bgColorPressed: Color,
        val bgColorDisabled: Color,
        val borderEnabled: Color,
        val borderFocused: Color,
        val borderHover: Color,
        val borderPressed: Color,
        val borderDisabled: Color,
        val textEnabled: Color,
        val textFocused: Color,
        val textHover: Color,
        val textPressed: Color,
        val textDisabled: Color
    )

    /**
     * AlertButton component colors.
     */
    data class AlertButton(
        val bgColorEnabled: Color,
        val bgColorFocused: Color,
        val bgColorHover: Color,
        val bgColorPressed: Color,
        val bgColorDisabled: Color,
        val borderEnabled: Color,
        val borderFocused: Color,
        val borderHover: Color,
        val borderPressed: Color,
        val borderDisabled: Color,
        val textEnabled: Color,
        val textFocused: Color,
        val textHover: Color,
        val textPressed: Color,
        val textDisabled: Color
    )

    /**
     * TextButton component colors.
     */
    data class TextButton(
        val bgColorPressed: Color,
        val bgColorHover: Color,
        val textEnabled: Color,
        val textFocused: Color,
        val textHover: Color,
        val textPressed: Color,
        val textDisabled: Color
    )

    /**
     * Snackbar component colors.
     */
    data class Snackbar(
        val bgColor: Color,
        val text: Color,
        val button: Color
    )

    /**
    * TextField component colors.
    */
    data class TextField(
        val focused: Color,
        val unfocusedContainer: Color,
        val unfocusedText: Color,
        val disabled: Color,
        val error: Color
    )

    /**
     * Forms component colors.
     */
    data class Forms(
        val controlActive: Color,
        val bgControlActive: Color,
        val textfieldActive: Color,
        val textfieldInactive: Color,
        val textfieldDisabled: Color
    )

    /**
     * Selectors component colors. (checkbox and radio button)
     */
    data class Selectors(
        val selected: Color,
        val checkmark: Color
    )

    /**
     * NumberRadioButton component colors.
     */
    data class NumberRadioButton(
        val background: Color,
        val borderSelected: Color,
        val borderUnselected: Color,
        val textSelected: Color,
        val textEnabled: Color,
        val textDisabled: Color
    )

    /**
     * Switch component colors.
     */
    data class Switch(
        val checkedThumbColor: Color,
        val checkedTrackColor: Color,
        val uncheckedThumbColor: Color,
        val uncheckedTrackColor: Color,
        val uncheckedBorderColor: Color
    )

    /**
     * Chip component colors.
     */
    data class Chip(
        val bgColorUnselected: Color,
        val bgColorSelected: Color,
        val borderSelected: Color,
        val borderUnselected: Color,
        val textUnselected: Color,
        val textSelected: Color
    )

    /**
     * TabBar component colors.
     */
    data class TabBar(
        val indicator: Color,
        val content: Color,
        val container: Color,
        val tabItemActive: Color,
        val tabItemInactive: Color
    )

    /**
     * FilledTabBar component colors.
     */
    data class FilledTabBar(
        val indicator: Color,
        val content: Color,
        val container: Color,
        val tabItemActive: Color,
        val tabItemInactive: Color
    )

    /**
     * Card component colors.
     */
    data class Card(
        val background: Color,
        val border: Color,
        val shadow: Color
    )

    /**
     * BottomBar component colors.
     */
    data class BottomBar(
        val active: Color,
        val inactive: Color,
        val background: Color,
        val selectedIcon: Color,
        val selectedBubble: Color
    )
}

/**
 * Common colors used across the app, such as black and white.
 *
 * @param black The color black, used for text and other elements.
 * @param white The color white, used for backgrounds and other elements.
 * @param transparent The color transparent, used for overlays and other elements.
 */
data class Common(
    val black: Color,
    val white: Color,
    val transparent: Color
)

/**
 * Primary color used for main highlights.
 *
 * @param main The main primary color.
 * @param light A lighter shade of the primary color, used for hover or focus states.
 * @param dark A darker shade of the primary color, used for pressed or selected states.
 * @param contrastText The color used for text that appears on top of the primary color, ensuring good contrast.
 */
data class Primary(
    val main: Color,
    val light: Color,
    val dark: Color,
    val contrastText: Color
)

/**
 * Secondary color used for secondary highlights.
 *
 * @param main The main secondary color.
 * @param light A lighter shade of the secondary color, used for hover or focus states.
 * @param dark A darker shade of the secondary color, used for pressed or selected states.
 * @param contrastText The color used for text that appears on top of the secondary color, ensuring good contrast.
 */
data class Secondary(
    val main: Color,
    val light: Color,
    val dark: Color,
    val contrastText: Color
)

/**
 * Tertiary color used for additional highlights.
 *
 * @param main The main tertiary color.
 * @param light A lighter shade of the tertiary color, used for hover or focus states.
 * @param dark A darker shade of the tertiary color, used for pressed or selected states.
 * @param contrastText The color used for text that appears on top of the tertiary color, ensuring good contrast.
 */
data class Tertiary(
    val main: Color,
    val light: Color,
    val dark: Color,
    val contrastText: Color
)

/**
 * Color used to indicate errors or critical issues.
 *
 * @param main The main error color.
 * @param light A lighter shade of the error color, used for hover or focus states.
 * @param dark A darker shade of the error color, used for pressed or selected states.
 * @param contrastText The color used for text that appears on top of the error color, ensuring good contrast.
 */
data class Error(
    val main: Color,
    val light: Color,
    val dark: Color,
    val contrastText: Color
)

/**
 * Color used to indicate warnings or important notices.
 *
 * @param main The main warning color.
 * @param light A lighter shade of the warning color, used for hover or focus states.
 * @param dark A darker shade of the warning color, used for pressed or selected states.
 * @param contrastText The color used for text that appears on top of the warning color, ensuring good contrast.
 */
data class Warning(
    val main: Color,
    val light: Color,
    val dark: Color,
    val contrastText: Color
)

/**
 * Color used to indicate informational messages.
 *
 * @param main The main info color.
 * @param light A lighter shade of the info color, used for hover or focus states.
 * @param dark A darker shade of the info color, used for pressed or selected states.
 * @param contrastText The color used for text that appears on top of the info color, ensuring good contrast.
 */
data class Info(
    val main: Color,
    val light: Color,
    val dark: Color,
    val contrastText: Color
)

/**
 * Color used to indicate successful actions or states.
 *
 * @param main The main success color.
 * @param light A lighter shade of the success color, used for hover or focus states.
 * @param dark A darker shade of the success color, used for pressed or selected states.
 * @param contrastText The color used for text that appears on top of the success color, ensuring good contrast.
 */
data class Success(
    val main: Color,
    val light: Color,
    val dark: Color,
    val contrastText: Color
)

/**
 * Color used for links and clickable text.
 *
 * @param main The main link color.
 * @param light A lighter shade of the link color, used for hover or focus states.
 * @param dark A darker shade of the link color, used for pressed or selected states.
 * @param contrastText The color used for text that appears on top of the link color, ensuring good contrast.
 */
data class Link(
    val main: Color,
    val light: Color,
    val dark: Color,
    val contrastText: Color
)

/**
 * Color used for primary actions, like buttons.
 *
 * @param main The main primary action color.
 * @param light A lighter shade of the primary action color, used for hover or focus states.
 * @param dark A darker shade of the primary action color, used for pressed or selected states.
 * @param contrastText The color used for text that appears on top of the primary action color, ensuring good contrast.
 */
data class PrimaryAction(
    val main: Color,
    val light: Color,
    val dark: Color,
    val contrastText: Color
)

/**
 * Shades of grey used for various UI elements. Goes from lightest (50) to darkest (900).
 */
data class Grey(
    val g50: Color,
    val g100: Color,
    val g200: Color,
    val g300: Color,
    val g400: Color,
    val g500: Color,
    val g600: Color,
    val g700: Color,
    val g800: Color,
    val g900: Color
)

/**
 * Colors used for text elements, including primary, secondary, and tertiary text.
 *
 * @param primary The primary text color.
 * @param secondary The secondary text color.
 * @param tertiary The tertiary text color.
 */
data class Text(
    val primary: Color,
    val secondary: Color,
    val tertiary: Color
)

/**
 * Colors used for different background elements, such as default, page, and section backgrounds.
 *
 * @param default The default background color.
 * @param pageColor The background color for pages.
 * @param mainColor The main background color used for main sections.
 * @param primary The primary background color used for highlights.
 * @param secondary The secondary background color used for additional highlights.
 * @param tertiary The tertiary background color used for less prominent sections.
 * @param error The background color used to indicate errors or critical issues.
 * @param warning The background color used to indicate warnings or important notices.
 * @param info The background color used to indicate informational messages.
 * @param success The background color used to indicate successful actions or states.
 */
data class Background(
    val default: Color,
    val pageColor: Color,
    val mainColor: Color,
    val primary: Color,
    val secondary: Color,
    val tertiary: Color,
    val error: Color,
    val warning: Color,
    val info: Color,
    val success: Color
)

//@OptIn(ExperimentalLayoutApi::class)
//@UiPreview
//@Composable
//@FreyjaEntry(name = "Color palette: general colors", category = FreyjaCatalogConstants.Categories.COLORS)
//fun ColorPalettePreview() {
//    // Create a preview with all the colors in the color palette for the Local AppTheme, grouped by their type. Also add names.
//    val colorPalette = LocalTheme.current.colors.palette
//    val colorPaletteColors = getColorPaletteColors(colorPalette)
//
//    UiPreviewLayout {
//        Column(
//            verticalArrangement = Arrangement.spacedBy(24.dp)
//        ) {
//            PreviewColorPalette("Color Palette", colorPaletteColors)
//        }
//    }
//}

//@OptIn(ExperimentalLayoutApi::class)
//@UiPreview
//@Composable
//@FreyjaEntry(name = "Color palette: component colors", category = FreyjaCatalogConstants.Categories.COLORS)
//fun ComponentColorsPalettePreview() {
//    // Create a preview with all the colors in the color palette for the Local AppTheme, grouped by their type. Also add names.
//    val componentColorsPalette = LocalTheme.current.colors.components
//    val componentColors = getColorPaletteColors(componentColorsPalette)
//
//    UiPreviewLayout {
//        Column(
//            verticalArrangement = Arrangement.spacedBy(24.dp)
//        ) {
//            PreviewColorPalette("Component colors", componentColors)
//        }
//    }
//}
//
//@Composable
//@OptIn(ExperimentalLayoutApi::class)
//private fun PreviewColorPalette(name: String, colors: List<Pair<String, List<Pair<String, Color>>>>) {
//    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
//        Text(
//            text = name,
//            fontSize = 20.sp,
//            fontWeight = FontWeight.Bold
//        )
//
//        colors.forEach { (colorGroupName, colorPairs) ->
//            Column(modifier = Modifier.fillMaxWidth()) {
//                Text(
//                    text = colorGroupName
//                )
//
//                Spacer(modifier = Modifier.height(12.dp))
//
//                FlowRow(
//                    horizontalArrangement = Arrangement.spacedBy(8.dp),
//                    verticalArrangement = Arrangement.spacedBy(8.dp),
//                    maxItemsInEachRow = 3
//                ) {
//                    colorPairs.forEach { (colorName, colorValue) ->
//                        val cornerSizeDp = 4.dp
//                        Box(
//                            modifier = Modifier
//                                .height(50.dp)
//                                .fillMaxWidth(0.319f)
//                                .background(color = colorValue, shape = RoundedCornerShape(cornerSizeDp))
//                                .border(
//                                    width = 1.dp,
//                                    color = Color(0x7f7f7f7f),
//                                    shape = RoundedCornerShape(cornerSizeDp)
//                                )
//                        ) {
//                            Text(
//                                modifier = Modifier.padding(8.dp),
//                                color = colorValue.getContrastColor(),
//                                text = colorName
//                            )
//                        }
//                    }
//                }
//            }
//        }
//    }
//}
//
//@Composable
//private fun <T> getColorPaletteColors(item: T): List<Pair<String, List<Pair<String, Color>>>> = item!!::class.declaredMemberProperties
//    .map { colorGroupProperty ->
//        val colorGroupName = colorGroupProperty.name
//        val colorGroupClass = colorGroupProperty.returnType.jvmErasure
//
//        val colorPairs = colorGroupClass.declaredMemberProperties.map { colorProperty ->
//            val colorName = colorProperty.name
//
//            @Suppress("UNCHECKED_CAST")
//            val colorValue = (colorProperty.apply { javaField?.isAccessible = true } as KProperty1<Any, Color>)
//                .get(colorGroupProperty.getter.call(item)!!)
//            colorName to colorValue
//        }
//
//        colorGroupName to colorPairs
//    }
