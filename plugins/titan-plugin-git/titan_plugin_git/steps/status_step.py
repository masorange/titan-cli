# plugins/titan-plugin-git/titan_plugin_git/steps/status_step.py
from titan_cli.engine import (
    WorkflowContext,
    WorkflowResult,
    Success,
    Error
)
from titan_cli.messages import msg as global_msg
from ..messages import msg

def get_git_status_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Retrieves the current git status and saves it to the context.

    Requires:
        ctx.git: An initialized GitClient.

    Outputs (saved to ctx.data):
        git_status (GitStatus): The full git status object, which includes the `is_clean` flag.

    Returns:
        Success: If the status was retrieved successfully.
        Error: If the GitClient is not available or the git command fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    if not ctx.git:
        return Error(msg.Steps.Status.GIT_CLIENT_NOT_AVAILABLE)

    # Begin step container
    ctx.textual.begin_step("Check Git Status")

    try:
        status = ctx.git.get_status()

        # If there are uncommitted changes, show text (border will be green on success)
        if not status.is_clean:
            ctx.textual.warning_text(global_msg.Workflow.UNCOMMITTED_CHANGES_WARNING)
            message = msg.Steps.Status.STATUS_RETRIEVED_WITH_UNCOMMITTED
        else:
            # Show text for clean working directory (border will be green)
            ctx.textual.success_text(msg.Steps.Status.WORKING_DIRECTORY_IS_CLEAN)
            message = msg.Steps.Status.WORKING_DIRECTORY_IS_CLEAN

        # End step container with success
        ctx.textual.end_step("success")

        return Success(
            message=message,
            metadata={"git_status": status}
        )
    except Exception as e:
        # End step container with error
        ctx.textual.end_step("error")
        return Error(msg.Steps.Status.FAILED_TO_GET_STATUS.format(e=e))
