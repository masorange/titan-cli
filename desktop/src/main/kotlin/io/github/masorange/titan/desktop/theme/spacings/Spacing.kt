package io.github.masorange.titan.desktop.theme.spacings

import androidx.compose.ui.unit.dp

/**
 * Standard spacing used for all components and screens of the app
 */
object Spacing {
    val s0 = 0.dp
    val s1 = 2.dp
    val s2 = 4.dp
    val s3 = 6.dp
    val s4 = 8.dp
    val s5 = 12.dp
    val s6 = 16.dp
    val s7 = 20.dp
    val s8 = 24.dp
    val s9 = 32.dp
    val s10 = 40.dp
    val s11 = 48.dp
    val s12 = 56.dp
    val s13 = 64.dp
    val s14 = 72.dp
    val s15 = 80.dp
}

//@OptIn(ExperimentalLayoutApi::class)
//@Composable
//@UiPreview
//@FreyjaEntry(name = "Spacings", category = FreyjaCatalogConstants.Categories.SPACINGS)
//fun SpacingPreview() {
//    // Create a preview with boxes with the size of the spacings
//    val spacings = Spacing::class.declaredMemberProperties.map { property ->
//        val name = property.name
//        val spacing = property.get(Spacing) as Dp
//
//        name to spacing
//    }.sortedBy { it.second }
//
//    UiPreviewLayout {
//        FlowRow(
//            horizontalArrangement = Arrangement.spacedBy(8.dp),
//            verticalArrangement = Arrangement.spacedBy(16.dp),
//            maxItemsInEachRow = 3
//        ) {
//            // Create a box for each spacing
//            spacings.forEach { (name, spacing) ->
//                Column {
//                    // Display the name of the spacing
//                    Text(
//                        text = name
//                    )
//
//                    Box(
//                        modifier = Modifier
//                            .size(spacing)
//                            .border(
//                                width = 1.dp,
//                                color = Color(0x7f7f7f7f)
//                            )
//                            .background(LocalTheme.current.colors.palette.primary.main)
//                    )
//                }
//            }
//        }
//    }
//}
