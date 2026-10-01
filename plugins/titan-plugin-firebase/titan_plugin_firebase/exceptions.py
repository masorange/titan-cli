"""Exceptions raised inside the Firebase plugin."""

from __future__ import annotations

from typing import Optional


class FirebaseError(Exception):
    """Base error for the Firebase plugin."""


class FirebaseConfigurationError(FirebaseError):
    """Raised when the plugin configuration cannot be used."""


class FirebaseAuthUnavailableError(FirebaseError):
    """Raised when no Application Default Credentials can be resolved."""


class FirebaseApiError(FirebaseError):
    """
    Raised when the Remote Config REST API answers with a failure.

    Carries the HTTP status so services can map concurrency (409) and
    permission (403) cases to distinct, actionable results.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        detail: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail
