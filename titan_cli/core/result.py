"""
Client Result Types

Generic result wrapper for client operations across all plugins.
Provides type-safe error handling without exceptions.

Inspired by Rust's Result<T, E> and the WorkflowResult pattern.

NOTE: This is ONLY for official Titan plugins (Jira, GitHub, Git).
Custom user steps are free to use any pattern they want.
"""

from dataclasses import dataclass
from typing import TypeVar, Generic, Optional

T = TypeVar('T')


@dataclass
class ClientSuccess(Generic[T]):
    """
    Successful client operation result.

    Contains the data and an optional success message.

    Examples:
        >>> result = ClientSuccess(data=issue, message="Issue retrieved")
        >>> print(result.data.key)
        'PROJ-123'
    """
    data: T
    message: str = ""


@dataclass
class ClientError:
    """
    Failed client operation result.

    Contains error information without raising an exception.

    Args:
        error_message: Human-readable description of what failed (no sensitive data).
        error_code: Structured code for programmatic handling (e.g. "NOT_FOUND").
        log_level: How the decorator should log this error.
                   Use "warning" for expected/recoverable cases (branch not found,
                   invalid transition). Use "error" for unexpected failures (API down,
                   auth error, network timeout). Defaults to "error".
        details: Optional dict with extra diagnostic context.
    """
    error_message: str
    error_code: Optional[str] = None
    log_level: str = "error"
    details: Optional[dict] = None


# Type alias for client results
# Usage: ClientResult[UIJiraIssue], ClientResult[UIPullRequest], etc.
ClientResult = ClientSuccess[T] | ClientError


__all__ = [
    "ClientSuccess",
    "ClientError",
    "ClientResult",
]
