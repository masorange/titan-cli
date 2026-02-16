# plugins/titan-plugin-git/titan_plugin_git/steps/status_step.py
from titan_cli.engine import (
    WorkflowContext,
    WorkflowResult,
    Success,
    Error,
    Exit
)
from titan_cli.core.result import ClientSuccess, ClientError
from titan_cli.messages import msg as global_msg
from ..messages import msg

def get_git_status_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Retrieves the current git status and saves it to the context.

    Behavior:
        - If there are uncommitted changes: Returns Success and continues workflow
        - If working directory is clean: Returns Exit (stops workflow - nothing to commit)

    Requires:
        ctx.git: An initialized GitClient.

    Outputs (saved to ctx.data):
        git_status (GitStatus): The full git status object, which includes the `is_clean` flag.

    Returns:
        Success: If there are changes to commit (workflow continues)
        Exit: If working directory is clean (workflow stops - nothing to commit)
        Error: If the GitClient is not available or the git command fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    if not ctx.git:
        return Error(msg.Steps.Status.GIT_CLIENT_NOT_AVAILABLE)

    # Begin step container
    ctx.textual.begin_step("Check Git Status")

    # Get status using ClientResult pattern
    result = ctx.git.get_status()

    match result:
        case ClientSuccess(data=status):
            # If there are uncommitted changes, continue with workflow
            if not status.is_clean:
                ctx.textual.warning_text(global_msg.Workflow.UNCOMMITTED_CHANGES_WARNING)
                message = msg.Steps.Status.STATUS_RETRIEVED_WITH_UNCOMMITTED
                ctx.textual.end_step("success")

                return Success(
                    message=message,
                    metadata={"git_status": status}
                )
            else:
                # Working directory is clean - exit workflow (nothing to commit)
                ctx.textual.success_text(msg.Steps.Status.WORKING_DIRECTORY_IS_CLEAN)
                ctx.textual.text("")
                ctx.textual.dim_text("Nothing to commit. Skipping workflow.")
                ctx.textual.end_step("success")

                # Exit workflow early (not an error)
                return Exit("No changes to commit", metadata={"git_status": status})

        case ClientError(error_message=err):
            # End step container with error
            ctx.textual.end_step("error")
            return Error(msg.Steps.Status.FAILED_TO_GET_STATUS.format(e=err))
