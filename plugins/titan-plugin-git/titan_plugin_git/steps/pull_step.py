"""
Pull from Git remote.
"""

from typing import Optional
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_plugin_git.exceptions import GitError


def pull_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Pull from Git remote.

    Inputs (from ctx.data):
        remote (str, optional): Remote name (defaults to "origin")
        branch (str, optional): Branch name (defaults to current branch)

    Returns:
        Success: Pull completed successfully
        Error: Git operation failed
    """
    if ctx.textual:
        ctx.textual.begin_step("Pull from Remote")

    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    if not ctx.git:
        ctx.textual.error_text("Git client not available in context")
        ctx.textual.end_step("error")
        return Error("Git client not available in context")

    try:
        # Get params from context (optional)
        remote = ctx.get("remote", "origin")
        branch: Optional[str] = ctx.get("pull_branch")  # Optional, defaults to current

        ctx.textual.text("")
        if branch:
            ctx.textual.dim_text(f"Pulling {remote}/{branch}...")
        else:
            ctx.textual.dim_text(f"Pulling from {remote}...")

        # Pull
        try:
            with ctx.textual.loading("Pulling from remote..."):
                ctx.git.pull(remote=remote, branch=branch)
            ctx.textual.success_text(f"✓ Pulled from {remote}")
        except GitError as e:
            ctx.textual.text("")
            ctx.textual.error_text(f"Failed to pull: {str(e)}")
            ctx.textual.end_step("error")
            return Error(f"Failed to pull: {str(e)}")

        ctx.textual.text("")
        ctx.textual.end_step("success")
        return Success(
            f"Pulled from {remote}",
            metadata={"remote": remote, "branch": branch}
        )

    except Exception as e:
        ctx.textual.text("")
        ctx.textual.error_text(f"Failed to pull: {str(e)}")
        ctx.textual.text("")
        ctx.textual.end_step("error")
        return Error(f"Failed to pull: {str(e)}")


__all__ = ["pull_step"]
