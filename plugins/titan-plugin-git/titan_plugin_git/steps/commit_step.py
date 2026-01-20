# plugins/titan-plugin-git/titan_plugin_git/steps/commit_step.py
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.engine.results import Skip
from titan_plugin_git.exceptions import GitClientError, GitCommandError
from titan_plugin_git.messages import msg
from titan_cli.ui.tui.widgets import Panel


def create_git_commit_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Creates a git commit.
    Skips if the working directory is clean or if a commit was already created.

    Requires:
        ctx.git: An initialized GitClient.

    Inputs (from ctx.data):
        git_status (GitStatus): The git status object, used to check if the working directory is clean.
        commit_message (str): The message for the commit.
        all_files (bool, optional): Whether to commit all modified and new files. Defaults to True.
        commit_files (list, optional): List of specific files to commit (without staging). Overrides all_files.
        commit_hash (str, optional): If present, indicates a commit was already created.

    Outputs (saved to ctx.data):
        commit_hash (str): The hash of the created commit.

    Returns:
        Success: If the commit was created successfully.
        Error: If the GitClient is not available, or the commit operation fails.
        Skip: If there are no changes to commit or a commit was already created.
    """
    # Skip if there's nothing to commit
    git_status = ctx.data.get("git_status")
    if git_status and git_status.is_clean:
        if ctx.textual:
            ctx.textual.mount(
                Panel(
                    text=msg.Steps.Commit.WORKING_DIRECTORY_CLEAN,
                    panel_type="info"
                )
            )
        elif ctx.ui:
            ctx.ui.panel.print(
                msg.Steps.Commit.WORKING_DIRECTORY_CLEAN,
                panel_type="info"
            )
        return Skip(msg.Steps.Commit.WORKING_DIRECTORY_CLEAN)

    if not ctx.git:
        return Error(msg.Steps.Commit.GIT_CLIENT_NOT_AVAILABLE)

    # SAFETY CHECK: Prevent commits on protected branches
    current_branch = ctx.git.get_current_branch()
    protected_branches = ['master', 'main', 'develop']
    if current_branch in protected_branches:
        error_msg = f"🚨 SAFETY CHECK FAILED: Cannot commit directly to protected branch '{current_branch}'"
        if ctx.textual:
            ctx.textual.mount(
                Panel(
                    text=error_msg,
                    panel_type="error"
                )
            )
        elif ctx.ui:
            ctx.ui.panel.print(error_msg, panel_type="error")
        return Error(error_msg)

    commit_message = ctx.get('commit_message')
    if not commit_message:
        if ctx.textual:
            ctx.textual.mount(
                Panel(
                    text=msg.Steps.Commit.NO_COMMIT_MESSAGE,
                    panel_type="info"
                )
            )
        elif ctx.ui:
            ctx.ui.panel.print(
                msg.Steps.Commit.NO_COMMIT_MESSAGE,
                panel_type="info"
            )
        return Skip(msg.Steps.Commit.NO_COMMIT_MESSAGE)

    commit_files = ctx.get('commit_files')
    all_files = ctx.get('all_files', True)

    try:
        # If specific files are provided, use them (overrides all_files)
        if commit_files:
            commit_hash = ctx.git.commit(message=commit_message, files=commit_files)
        else:
            commit_hash = ctx.git.commit(message=commit_message, all=all_files)

        # Show success panel
        if ctx.textual:
            ctx.textual.mount(
                Panel(
                    text=f"Commit created: {commit_hash[:7]}",
                    panel_type="success"
                )
            )
        elif ctx.ui:
            ctx.ui.panel.print(
                f"Commit created: {commit_hash[:7]}",
                panel_type="success"
            )

        return Success(
            message=msg.Steps.Commit.COMMIT_SUCCESS.format(commit_hash=commit_hash),
            metadata={"commit_hash": commit_hash}
        )
    except GitClientError as e:
        return Error(msg.Steps.Commit.CLIENT_ERROR_DURING_COMMIT.format(e=e))
    except GitCommandError as e:
        return Error(msg.Steps.Commit.COMMAND_FAILED_DURING_COMMIT.format(e=e))
    except Exception as e:
        return Error(msg.Steps.Commit.UNEXPECTED_ERROR_DURING_COMMIT.format(e=e))
