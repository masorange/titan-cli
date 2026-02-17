"""
Logging configuration for Titan CLI using structlog.

Provides structured logging with:
- Development mode: Colorized console output + JSON file logs
- Production mode: Minimal console + JSON file logs
- Automatic rotation (10MB per file, keep 5 files)
- XDG-compliant log directory (~/.local/state/titan/logs/)
"""

import sys
import os
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

import structlog


def setup_logging(
    verbose: bool = False,
    debug: bool = False,
    log_file: Optional[Path] = None,
) -> structlog.BoundLogger:
    """
    Configure structlog for Titan CLI.

    Args:
        verbose: Enable verbose output (INFO level)
        debug: Enable debug mode (DEBUG level + detailed output)
        log_file: Optional custom log file path (default: ~/.local/state/titan/logs/titan.log)

    Returns:
        Configured structlog logger instance

    Example:
        logger = setup_logging(debug=True)
        logger.info("titan_started", version="0.1.11")
        logger.error("operation_failed", error="Connection timeout", step="fetch_issues")
    """
    # Determine log level
    log_level = logging.DEBUG if debug else (logging.INFO if verbose else logging.WARNING)

    # Determine if we're in development mode
    is_dev = _is_development_mode(debug)

    # Setup file logging
    _setup_file_handler(log_file, debug)

    # Setup console logging
    _setup_console_handler(log_level, is_dev)

    # Configure structlog
    _configure_structlog(is_dev)

    # Get logger and log startup
    logger = structlog.get_logger("titan")
    logger.info(
        "logging_initialized",
        mode="development" if is_dev else "production",
        log_level=logging.getLevelName(log_level),
        log_file=str(_get_log_file_path(log_file)),
    )

    return logger


def _is_development_mode(debug: bool) -> bool:
    """
    Determine if we're in development mode.

    Checks:
    1. TITAN_ENV environment variable
    2. Debug flag
    3. Running in TTY (terminal)

    Returns:
        True if development mode, False otherwise
    """
    if os.getenv("TITAN_ENV") == "development":
        return True
    if debug:
        return True
    if sys.stdout.isatty():
        return True
    return False


def _get_log_file_path(custom_path: Optional[Path] = None) -> Path:
    """
    Get log file path (XDG-compliant).

    Default: ~/.local/state/titan/logs/titan.log

    Args:
        custom_path: Optional custom path

    Returns:
        Path to log file
    """
    if custom_path:
        return custom_path

    # XDG Base Directory: logs go in ~/.local/state/
    log_dir = Path.home() / ".local" / "state" / "titan" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    return log_dir / "titan.log"


def _setup_file_handler(log_file: Optional[Path], debug: bool) -> None:
    """
    Setup file handler with rotation.

    Configuration:
    - Rotation: 10 MB per file
    - Retention: Keep 5 files (50 MB total)
    - Format: JSON (structured)
    - Encoding: UTF-8
    """
    file_path = _get_log_file_path(log_file)

    file_handler = RotatingFileHandler(
        file_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,  # Keep 5 files
        encoding="utf-8",
    )

    # File always logs at DEBUG in dev, INFO in prod
    file_handler.setLevel(logging.DEBUG if debug else logging.INFO)

    # Add to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.DEBUG)  # Root logger accepts all, handlers filter


def _setup_console_handler(log_level: int, is_dev: bool) -> None:
    """
    Setup console handler.

    Development: Colorized, detailed output
    Production: Minimal, ERROR level only
    """
    console_handler = logging.StreamHandler(sys.stdout)

    if is_dev:
        # Dev: show everything based on log_level
        console_handler.setLevel(log_level)
    else:
        # Prod: only show errors on console
        console_handler.setLevel(logging.ERROR)

    # Format is handled by structlog processors
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    # Add to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)


def _configure_structlog(is_dev: bool) -> None:
    """
    Configure structlog processors and factory.

    Development: ConsoleRenderer (colorized, human-readable)
    Production: JSONRenderer (machine-parseable)
    """
    # Shared processors (before final rendering)
    shared_processors = [
        structlog.contextvars.merge_contextvars,  # Add context variables
        structlog.stdlib.add_log_level,  # Add log level
        structlog.stdlib.add_logger_name,  # Add logger name
        structlog.processors.StackInfoRenderer(),  # Stack info if available
    ]

    # Choose final renderer based on mode
    # NOTE: Only final rendering processors here, shared_processors go in main configure
    if is_dev:
        # Development: colorized console output
        console_processors = [
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),  # Human-readable timestamp
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            ),
        ]
        file_processors = [
            structlog.processors.TimeStamper(fmt="iso"),  # ISO for file
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Production: JSON for both
        json_processors = [
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
        console_processors = json_processors
        file_processors = json_processors

    # Configure structlog
    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure formatters for stdlib integration
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
        ]
        + console_processors,  # Include ALL processors (TimeStamper + Renderer)
    )

    file_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
        ]
        + file_processors,  # Include ALL processors
    )

    # Apply formatters to specific handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            # Console handler
            handler.setFormatter(console_formatter)
        else:
            # File handler
            handler.setFormatter(file_formatter)


def get_logger(name: str = "titan") -> structlog.BoundLogger:
    """
    Get a configured logger instance.

    This should be called AFTER setup_logging() has been called.

    Args:
        name: Logger name (default: "titan")

    Returns:
        Configured structlog logger

    Example:
        from titan_cli.core.logging import get_logger

        logger = get_logger(__name__)
        logger.info("step_started", step="commit", branch="main")
    """
    return structlog.get_logger(name)


def disable_console_logging() -> None:
    """
    Disable console logging (only log to file).

    This is used in production mode when launching the Textual TUI.
    In production, console logs would be hidden by the TUI anyway,
    so we disable them to save resources.

    In debug mode, console logging stays enabled because Textual
    devtools will capture and display them in a separate console.

    After calling this, logs will only go to the file handler.
    """
    root_logger = logging.getLogger()

    # Remove console handler (StreamHandler that's not a FileHandler)
    for handler in root_logger.handlers[:]:  # [:] creates a copy for safe iteration
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.FileHandler
        ):
            root_logger.removeHandler(handler)
