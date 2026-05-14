"""Custom exceptions for the PoEditor plugin."""


class PoEditorError(Exception):
    """Base exception for PoEditor plugin."""

    pass


class PoEditorConfigurationError(PoEditorError):
    """Configuration is invalid or incomplete."""

    pass


class PoEditorClientError(PoEditorError):
    """PoEditor client not initialized or unavailable."""

    pass


class PoEditorAPIError(PoEditorError):
    """API communication failed."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response: dict | None = None,
    ):
        """Initialize API error with details.

        Args:
            message: Error message
            status_code: HTTP status code if available
            response: Raw API response if available
        """
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(message)
