# plugins/titan-plugin-git/titan_plugin_git/steps/branch_steps.py
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_plugin_git.messages import msg

def get_current_branch_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Gets the current git branch and saves it to the context as 'pr_head_branch'.

    Sets:
        ctx.data['pr_head_branch']: The name of the current branch.
    """
    if not ctx.git:
        return Error(msg.Steps.Status.GIT_CLIENT_NOT_AVAILABLE)
    
    try:
        current_branch = ctx.git.get_current_branch()
        return Success(
            f"Current branch is '{current_branch}'",
            metadata={"pr_head_branch": current_branch}
        )
    except Exception as e:
        return Error(f"Failed to get current branch: {e}", exception=e)

def get_base_branch_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Gets the configured main/base branch and saves it to the context as 'pr_base_branch'.

    Sets:
        ctx.data['pr_base_branch']: The name of the base branch.
    """
    if not ctx.git:
        return Error(msg.Steps.Status.GIT_CLIENT_NOT_AVAILABLE)

    try:
        base_branch = ctx.git.main_branch
        return Success(
            f"Base branch is '{base_branch}'",
            metadata={"pr_base_branch": base_branch}
        )
    except Exception as e:
        return Error(f"Failed to get base branch: {e}", exception=e)
