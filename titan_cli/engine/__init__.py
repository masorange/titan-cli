"""
Titan CLI Workflow Engine

This module provides the execution engine for composing and running workflows
using the Atomic Steps Pattern.

Core components:
- WorkflowResult types (Success, Error, Skip)
- WorkflowContext for dependency injection
- WorkflowContextBuilder for fluent API
- WorkflowExecutor for executing YAML workflows (see workflow_executor.py)
"""

from .results import (
    WorkflowResult,
    Success,
    Error,
    Skip,
    is_success,
    is_error,
    is_skip,
)
from .context import WorkflowContext
from .builder import WorkflowContextBuilder

__all__ = [
    # Result types
    "WorkflowResult",
    "Success",
    "Error",
    "Skip",
    # Helper functions
    "is_success",
    "is_error",
    "is_skip",
    # Context & builder
    "WorkflowContext",
    "WorkflowContextBuilder",
]
