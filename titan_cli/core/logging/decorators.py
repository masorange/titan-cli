"""
Logging decorators for automatic instrumentation.

Provides decorators to automatically log ClientResult operations
and other common patterns.
"""

import contextlib
import contextvars
import functools
import time
from typing import Any, Callable, Iterator, TypeVar

from titan_cli.core.logging.config import get_logger
from titan_cli.core.result import ClientSuccess, ClientError


F = TypeVar('F', bound=Callable[..., Any])

_best_effort: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "titan_best_effort_operation", default=False
)


@contextlib.contextmanager
def best_effort_operation() -> Iterator[None]:
    """
    Mark client calls in this block as speculative, so a failure logs at debug.

    Only the caller knows an operation is optional. Speculative cleanup that
    fails is normal control flow, but `log_client_operation` sees the same
    `ClientError` either way and would report it at error — which is how
    removing a worktree that was never registered became the only error in an
    otherwise healthy run, and poisoned every "did this run fail?" check.
    """
    token = _best_effort.set(True)
    try:
        yield
    finally:
        _best_effort.reset(token)


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

                    case ClientError(error_message=error_message, error_code=error_code, log_level=log_level):
                        if _best_effort.get():
                            log_fn = logger.debug
                        elif log_level == "warning":
                            log_fn = logger.warning
                        else:
                            log_fn = logger.error
                        log_fn(
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
