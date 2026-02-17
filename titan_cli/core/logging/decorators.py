"""
Logging decorators for automatic instrumentation.

Provides decorators to automatically log ClientResult operations
and other common patterns.
"""

import functools
import time
from typing import Any, Callable, TypeVar

from titan_cli.core.logging.config import get_logger

F = TypeVar('F', bound=Callable[..., Any])


def log_client_operation(operation_name: str = None):
    """
    Decorator to automatically log ClientResult operations.

    Logs the start and result of operations that return ClientResult.
    - ClientSuccess: Logs at INFO level
    - ClientError: Logs at ERROR level
    - Exceptions: Logs with full traceback

    Args:
        operation_name: Optional custom name for the operation.
                       If not provided, uses function name.

    Usage:
        @log_client_operation("fetch_issues")
        def search_issues(self, jql: str) -> ClientResult[List[UIJiraIssue]]:
            ...

        # Or without custom name (uses function name)
        @log_client_operation()
        def get_status(self) -> ClientResult[UIGitStatus]:
            ...

    Example logs:
        # Start (DEBUG level)
        {"event": "search_issues_started", "jql": "project=ABC"}

        # Success (INFO level)
        {"event": "search_issues_success", "message": "Found 5 issues", "result_type": "List[UIJiraIssue]"}

        # Error (ERROR level)
        {"event": "search_issues_failed", "error": "Invalid JQL", "error_code": "JQL_ERROR"}
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Lazy import to avoid circular dependency
            from titan_cli.engine.results import ClientSuccess, ClientError

            logger = get_logger(func.__module__)
            op_name = operation_name or func.__name__

            # Extract meaningful kwargs for logging (skip 'self')
            log_kwargs = {k: v for k, v in kwargs.items() if k != 'self'}

            # Log operation start (DEBUG level)
            logger.debug(f"{op_name}_started", **log_kwargs)

            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                # Log based on ClientResult type
                match result:
                    case ClientSuccess(data=data, message=message):
                        # Get type name safely
                        data_type = type(data).__name__ if data is not None else "None"

                        logger.info(
                            f"{op_name}_success",
                            message=message,
                            result_type=data_type,
                            duration=round(duration, 3)
                        )

                    case ClientError(error_message=error_message, error_code=error_code):
                        logger.error(
                            f"{op_name}_failed",
                            error=error_message,
                            error_code=error_code,
                            duration=round(duration, 3)
                        )

                    case _:
                        # Not a ClientResult, just log completion
                        logger.debug(
                            f"{op_name}_completed",
                            duration=round(duration, 3)
                        )

                return result

            except Exception:
                duration = time.time() - start_time
                logger.exception(
                    f"{op_name}_exception",
                    duration=round(duration, 3)
                )
                raise

        return wrapper  # type: ignore
    return decorator
