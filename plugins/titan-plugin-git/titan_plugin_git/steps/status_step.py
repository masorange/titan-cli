# plugins/titan-plugin-git/titan_plugin_git/steps/status_step.py
from titan_cli.engine import (
    WorkflowContext, 
    WorkflowResult, 
    Success, 
    Error
)

def get_git_status_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    A workflow step that retrieves the current git status.
    
    Requires:
        ctx.git: An initialized GitClient.
    
    Sets:
        ctx.data['git_status']: The GitStatus object.
    
    Returns:
        Success: If the status was retrieved successfully.
        Error: If the GitClient is not available.
    """
    if not ctx.git:
        return Error("Git client is not available in the workflow context.")

    try:
        status = ctx.git.get_status()
        
        message = "Git status retrieved successfully."
        if not status.is_clean:
            message += " Working directory is not clean."
            
        return Success(
            message=message,
            metadata={"git_status": status}
        )
    except Exception as e:
        return Error(f"Failed to get git status: {e}")
