from titan_cli.core.errors import TitanError

class WorkflowError(TitanError):
    """Base exception for workflow-related errors."""
    pass

class WorkflowNotFoundError(WorkflowError):
    """Raised when a workflow or its base cannot be found."""
    pass

class WorkflowValidationError(WorkflowError):
    """Raised when a workflow configuration fails Pydantic validation."""
    pass

class WorkflowExecutionError(WorkflowError):
    """Raised when a workflow execution fails."""
    pass
