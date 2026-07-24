"""Firebase plugin exceptions."""


class FirebaseConfigurationError(Exception):
    """Raised when Firebase plugin configuration is invalid."""


class FirebaseClientError(Exception):
    """Raised when Firebase client operations fail."""


class FirebaseAuthRejectedError(FirebaseClientError):
    """Raised when Firebase rejects the resolved OAuth credential."""

    def __init__(self, message: str, *, auth_source: str | None = None) -> None:
        super().__init__(message)
        self.auth_source = auth_source
