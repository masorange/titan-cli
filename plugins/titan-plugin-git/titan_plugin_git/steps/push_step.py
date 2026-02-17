# plugins/titan-plugin-git/titan_plugin_git/steps/push_step.py
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_git.messages import msg

def create_git_push_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Pushes changes to a remote repository.

    Requires (from ctx.data):
        remote (str, optional): The name of the remote to push to. Defaults to the client's default remote.
        branch (str, optional): The name of the branch to push. Defaults to the current branch.
        set_upstream (bool, optional): Whether to set the upstream tracking branch. Defaults to False.
        push_tags (bool, optional): Whether to push tags along with the branch. Defaults to False.

    Requires:
        ctx.git: An initialized GitClient.

    Outputs (saved to ctx.data):
        pr_head_branch (str): The name of the branch that was pushed.

    Returns:
        Success: If the push was successful.
        Error: If the push operation fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    if not ctx.git:
        return Error(msg.Steps.Push.GIT_CLIENT_NOT_AVAILABLE)

    # Begin step container
    ctx.textual.begin_step("Push changes to remote")

    # Get params from context
    remote = ctx.get('remote')
    branch = ctx.get('branch')
    set_upstream = ctx.get('set_upstream', False)
    push_tags = ctx.get('push_tags', False)

    # Use defaults from the GitClient if not provided in the context
    remote_to_use = remote or ctx.git.default_remote

    # Get current branch if not provided
    if not branch:
        branch_result = ctx.git.get_current_branch()
        match branch_result:
            case ClientSuccess(data=current_branch):
                branch_to_use = current_branch
            case ClientError(error_message=err):
                ctx.textual.end_step("error")
                return Error(f"Failed to get current branch: {err}")
    else:
        branch_to_use = branch

    # Check if branch exists on remote
    exists_result = ctx.git.branch_exists_on_remote(branch=branch_to_use, remote=remote_to_use)
    match exists_result:
        case ClientSuccess(data=exists):
            # The first push of a branch should set the upstream
            if not exists:
                set_upstream = True
        case ClientError(error_message=err):
            ctx.textual.end_step("error")
            return Error(f"Failed to check remote branch: {err}")

    # Push branch (and tags if requested)
    push_result = ctx.git.push(
        remote=remote_to_use,
        branch=branch_to_use,
        set_upstream=set_upstream,
        tags=push_tags
    )

    match push_result:
        case ClientSuccess():
            # Show success message
            success_msg = f"Pushed to {remote_to_use}/{branch_to_use}"
            if push_tags:
                success_msg += " (with tags)"

            ctx.textual.success_text(success_msg)

            ctx.textual.end_step("success")
            return Success(
                message=msg.Git.PUSH_SUCCESS.format(remote=remote_to_use, branch=branch_to_use),
                metadata={"pr_head_branch": branch_to_use}
            )
        case ClientError(error_message=err):
            error_msg = msg.Steps.Push.PUSH_FAILED.format(e=err)
            ctx.textual.error_text(error_msg)
            ctx.textual.end_step("error")
            return Error(error_msg)
