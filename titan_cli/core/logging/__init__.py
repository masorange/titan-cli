"""
Logging subsystem for Titan CLI.

Provides structured logging with:
- Development vs Production modes
- File rotation and retention
- Automatic ClientResult tracking
- Workflow execution logging

Usage:
    from titan_cli.core.logging import setup_logging, get_logger

    # Setup (in cli.py)
    setup_logging(verbose=True, debug=False)

    # Get logger
    logger = get_logger(__name__)
    logger.info("operation_completed", items=5)
"""

from .config import setup_logging, get_logger, disable_console_logging
from .decorators import log_client_operation

__all__ = [
    "setup_logging",
    "get_logger",
    "disable_console_logging",
    "log_client_operation",
]
