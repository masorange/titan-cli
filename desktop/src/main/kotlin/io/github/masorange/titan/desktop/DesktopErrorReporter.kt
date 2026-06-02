package io.github.masorange.titan.desktop

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class DesktopError(
    val title: String,
    val message: String,
    val details: String,
)

object DesktopErrorReporter {
    private val _currentError = MutableStateFlow<DesktopError?>(null)
    val currentError: StateFlow<DesktopError?> = _currentError.asStateFlow()

    fun report(throwable: Throwable) {
        _currentError.value = DesktopError(
            title = throwable::class.simpleName ?: "Unexpected error",
            message = throwable.message ?: throwable.toString(),
            details = throwable.stackTraceToString(),
        )
    }

    fun dismiss() {
        _currentError.value = null
    }
}
