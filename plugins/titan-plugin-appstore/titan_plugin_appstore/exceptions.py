"""
Custom exceptions for App Store Connect plugin.
"""


class AppStoreConnectError(Exception):
    """Base exception for App Store Connect operations."""
    pass


class AuthenticationError(AppStoreConnectError):
    """Raised when authentication with App Store Connect fails."""
    pass


class APIError(AppStoreConnectError):
    """Raised when App Store Connect API returns an error."""

    def __init__(self, message: str, status_code: int = None, response_data: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class ValidationError(AppStoreConnectError):
    """Raised when input validation fails."""
    pass


class ResourceNotFoundError(AppStoreConnectError):
    """Raised when a requested resource is not found."""
    pass


class VersionConflictError(AppStoreConnectError):
    """Raised when trying to create a version that already exists."""
    pass


class ConfigurationError(AppStoreConnectError):
    """Raised when plugin configuration is invalid or missing."""
    pass
