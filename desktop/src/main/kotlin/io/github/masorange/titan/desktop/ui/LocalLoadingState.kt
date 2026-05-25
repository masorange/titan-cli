package io.github.masorange.titan.desktop.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.compositionLocalOf

/**
 * Local loading [Boolean] param to track the state of each screen across the composition hierarchy.
 *
 * WARNING: This value MUST be used together with [withLocalLoadingState] together with a [MutableState] of a [Boolean] to receive
 * the proper updates when the state gets change and trigger any needed recomposition based on these values.
 *
 * See example:
 *  ```
 *  val isLoadingState = pepeStore.flow()
 *                                .select { it.task.isLoading || it.task.isEmpty }
 *                                .collectAsState(initial = true)
 *
 *  withLocalLoadingState(isLoadingState) {
 *        Button(
 *        text = "Potato",
 *        modifier = Modifier.clickable(enabled = LocalLoadingState.current
 *        )
 *  }
 *  ```
 */
val LocalLoadingState = compositionLocalOf { false }

/**
 * Method to provide the actual value of the [LocalLoadingState] for the whole content of the given composable.
 *
 * @param isLoading - actual value for [LocalLoadingState]. Keep in mind that if you want this value to get updated
 * and trigger recomposition you must provide a [MutableState] of a [Boolean].
 */
@Composable
fun withLocalLoadingState(isLoading: Boolean, content: @Composable () -> Unit) {
    CompositionLocalProvider(LocalLoadingState provides isLoading) {
        content()
    }
}
