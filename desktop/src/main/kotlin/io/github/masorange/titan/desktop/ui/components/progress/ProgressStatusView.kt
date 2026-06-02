package io.github.masorange.titan.desktop.ui.components.progress

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.LinearProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import io.github.masorange.titan.desktop.state.ProgressLifecycleState
import io.github.masorange.titan.desktop.state.SemanticContentVariant
import io.github.masorange.titan.desktop.theme.H3Text
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import io.github.masorange.titan.desktop.ui.DesktopPreview
import io.github.masorange.titan.desktop.ui.LocalTheme
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun ProgressStatusView(
    modifier: Modifier = Modifier,
    message: String,
    lifecycle: ProgressLifecycleState,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(color = LocalTheme.current.colors.ui.previewBackground)
            .padding(Spacing.s6),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        H3Text(text = message)
        Spacer(modifier = Modifier.height(Spacing.s3))
        if (lifecycle == ProgressLifecycleState.STARTED ||
            lifecycle == ProgressLifecycleState.UPDATED
        ) {
            LinearProgressIndicator(
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
fun SemanticContentVariant.toDisplayColor(): Color = when (this) {
    SemanticContentVariant.DEFAULT,
    SemanticContentVariant.UNKNOWN -> Color.Unspecified

    SemanticContentVariant.SUCCESS -> LocalTheme.current.colors.palette.success.main
    SemanticContentVariant.MUTED -> LocalTheme.current.colors.palette.text.secondary.copy(alpha = 0.8f)
    SemanticContentVariant.WARNING -> LocalTheme.current.colors.palette.warning.main
    SemanticContentVariant.ERROR -> LocalTheme.current.colors.palette.error.main
}

@Preview
@Composable
private fun ProgressStatusViewPreview() {
    DesktopPreview {
        ProgressStatusView(
            message = "Test",
            lifecycle = ProgressLifecycleState.STARTED
        )
    }
}
