package io.github.masorange.titan.desktop

import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Window
import androidx.compose.ui.window.WindowState
import androidx.compose.ui.window.application

fun main() = application {
    Window(
        onCloseRequest = ::exitApplication,
        title = "Titan Desktop PoC",
        state = WindowState(width = 1200.dp, height = 840.dp),
    ) {
        App()
    }
}
