# plugins/titan-plugin-git/titan_plugin_git/steps/branch_steps.py
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_git.messages import msg

def get_current_branch_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Retrieves the current git branch name and saves it to the context.

    Requires:
        ctx.git: An initialized GitClient.

    Outputs (saved to ctx.data):
        pr_head_branch (str): The name of the current branch, to be used as the head branch for a PR.

    Returns:
        Success: If the current branch was retrieved successfully.
        Error: If the GitClient is not available or the git command fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Begin step container
    ctx.textual.begin_step("Get Head Branch")

    if not ctx.git:
        error_msg = msg.Steps.Status.GIT_CLIENT_NOT_AVAILABLE
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)

    # Get current branch using ClientResult pattern
    result = ctx.git.get_current_branch()

    match result:
        case ClientSuccess(data=current_branch):
            success_msg = msg.Steps.Branch.GET_CURRENT_BRANCH_SUCCESS.format(branch=current_branch)
            ctx.textual.success_text(success_msg)
            ctx.textual.end_step("success")
            return Success(
                success_msg,
                metadata={"pr_head_branch": current_branch}
            )
        case ClientError(error_message=err):
            error_msg = msg.Steps.Branch.GET_CURRENT_BRANCH_FAILED.format(e=err)
            ctx.textual.error_text(error_msg)
            ctx.textual.end_step("error")
            return Error(error_msg)

def get_base_branch_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Retrieves the configured main/base branch name and saves it to the context.

    Requires:
        ctx.git: An initialized GitClient.

    Outputs (saved to ctx.data):
        pr_base_branch (str): The name of the base branch, to be used as the base branch for a PR.

    Returns:
        Success: If the base branch was retrieved successfully.
        Error: If the GitClient is not available or the git command fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Begin step container
    ctx.textual.begin_step("Get Base Branch")

    if not ctx.git:
        error_msg = msg.Steps.Status.GIT_CLIENT_NOT_AVAILABLE
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg)

    try:
        base_branch = ctx.git.main_branch
        success_msg = msg.Steps.Branch.GET_BASE_BRANCH_SUCCESS.format(branch=base_branch)
        ctx.textual.success_text(success_msg)
        ctx.textual.end_step("success")
        return Success(
            success_msg,
            metadata={"pr_base_branch": base_branch}
        )
    except Exception as e:
        error_msg = msg.Steps.Branch.GET_BASE_BRANCH_FAILED.format(e=e)
        ctx.textual.error_text(error_msg)
        ctx.textual.end_step("error")
        return Error(error_msg, exception=e)
