# plugins/titan-plugin-git/titan_plugin_git/steps/diff_summary_step.py
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from titan_cli.core.result import ClientSuccess, ClientError
from titan_plugin_git.messages import msg
from ..operations import format_diff_stat_display


def show_uncommitted_diff_summary(ctx: WorkflowContext) -> WorkflowResult:
    """
    Show summary of uncommitted changes (git diff --stat).

    Provides a visual overview of files changed and lines modified
    before generating commit messages.

    Returns:
        Success: Always (even if no changes, for workflow continuity)
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    if not ctx.git:
        return Error(msg.Steps.Push.GIT_CLIENT_NOT_AVAILABLE)

    # Begin step container
    ctx.textual.begin_step("Show Changes Summary")

    # Get diff stat for uncommitted changes using ClientResult pattern
    result = ctx.git.get_uncommitted_diff_stat()

    match result:
        case ClientSuccess(data=stat_output):
            if not stat_output or not stat_output.strip():
                ctx.textual.dim_text("No uncommitted changes to show")
                ctx.textual.end_step("success")
                return Success("No changes")

            # Show the stat summary with colors
            ctx.textual.text("")  # spacing
            ctx.textual.bold_text("Changes summary:")
            ctx.textual.text("")  # spacing

            # Format diff stat with colors and alignment using operations
            formatted_files, formatted_summary = format_diff_stat_display(stat_output)

            # Display aligned file changes
            for line in formatted_files:
                ctx.textual.text(f"  {line}")

            # Display summary lines
            for line in formatted_summary:
                ctx.textual.dim_text(f"  {line}")

            ctx.textual.text("")  # spacing

            # End step container with success
            ctx.textual.end_step("success")

            return Success("Diff summary displayed")

        case ClientError(error_message=err):
            # Don't fail the workflow, just skip
            ctx.textual.end_step("skip")
            return Skip(f"Could not show diff summary: {err}")


def show_branch_diff_summary(ctx: WorkflowContext) -> WorkflowResult:
    """
    Show summary of branch changes (git diff base...head --stat).

    Provides a visual overview of files changed between branches
    before generating PR descriptions.

    Inputs (from ctx.data):
        pr_head_branch (str): Head branch name

    Returns:
        Success: Always (even if no changes, for workflow continuity)
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Begin step container
    ctx.textual.begin_step("Show Branch Changes Summary")

    if not ctx.git:
        ctx.textual.error_text(msg.Steps.Push.GIT_CLIENT_NOT_AVAILABLE)
        ctx.textual.end_step("error")
        return Error(msg.Steps.Push.GIT_CLIENT_NOT_AVAILABLE)

    head_branch = ctx.get("pr_head_branch")
    if not head_branch:
        ctx.textual.dim_text("No head branch specified")
        ctx.textual.end_step("skip")
        return Skip("No head branch specified")

    base_branch = ctx.git.main_branch
    remote = ctx.git.default_remote

    # Get diff stat between branches using ClientResult pattern
    result = ctx.git.get_branch_diff_stat(base_branch, head_branch)

    match result:
        case ClientSuccess(data=stat_output):
            if not stat_output or not stat_output.strip():
                ctx.textual.dim_text(f"No changes between {remote}/{base_branch} and {head_branch}")
                ctx.textual.end_step("success")
                return Success("No changes")

            # Show the stat summary with colors
            ctx.textual.text("")  # spacing
            ctx.textual.bold_text(f"Changes in {head_branch} vs {remote}/{base_branch}:")
            ctx.textual.text("")  # spacing

            # Format diff stat with colors and alignment using operations
            formatted_files, formatted_summary = format_diff_stat_display(stat_output)

            # Display aligned file changes
            for line in formatted_files:
                ctx.textual.text(f"  {line}")

            # Display summary lines
            for line in formatted_summary:
                ctx.textual.dim_text(f"  {line}")

            ctx.textual.text("")  # spacing

            ctx.textual.end_step("success")
            return Success("Branch diff summary displayed")

        case ClientError(error_message=err):
            # Don't fail the workflow, just skip
            ctx.textual.warning_text(f"Could not show branch diff summary: {err}")
            ctx.textual.end_step("skip")
            return Skip(f"Could not show branch diff summary: {err}")


__all__ = ["show_uncommitted_diff_summary", "show_branch_diff_summary"]
