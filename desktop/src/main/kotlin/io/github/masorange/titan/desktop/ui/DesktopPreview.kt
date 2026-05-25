package io.github.masorange.titan.desktop.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp


@Composable
fun DesktopPreview(
    modifier: Modifier = Modifier,
    isLoading: Boolean = false,
    content: @Composable () -> Unit
) {
    withLocalTheme(theme = LocalTheme.current) {
        withLocalLoadingState(isLoading = isLoading) {
            Box(
                modifier = modifier
                    .background(LocalTheme.current.colors.palette.grey.g100)
                    .padding(16.dp)
            ) {
                content()
            }
        }
    }
}
