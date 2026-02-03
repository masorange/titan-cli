"""
Checkout a Git branch.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_plugin_git.exceptions import GitError


def checkout_branch_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Checkout a Git branch.

    Inputs (from ctx.data):
        branch (str): Branch name to checkout

    Returns:
        Success: Branch checked out successfully
        Error: Git operation failed
    """
    if ctx.textual:
        ctx.textual.begin_step("Checkout Branch")

    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    if not ctx.git:
        ctx.textual.error_text("Git client not available in context")
        ctx.textual.end_step("error")
        return Error("Git client not available in context")

    try:
        # Get branch from params, or use main_branch from git config
        branch = ctx.get("branch")
        if not branch:
            branch = ctx.git.main_branch
            ctx.textual.dim_text(f"Using main branch from config: {branch}")

        ctx.textual.text("")
        ctx.textual.dim_text(f"Checking out: {branch}")

        # Checkout branch
        try:
            ctx.git.checkout(branch)
            ctx.textual.success_text(f"✓ Checked out {branch}")
        except GitError as e:
            ctx.textual.text("")
            ctx.textual.error_text(f"Failed to checkout {branch}: {str(e)}")
            ctx.textual.end_step("error")
            return Error(f"Failed to checkout: {str(e)}")

        ctx.textual.text("")
        ctx.textual.end_step("success")
        return Success(
            f"Checked out {branch}",
            metadata={"branch": branch}
        )

    except Exception as e:
        ctx.textual.text("")
        ctx.textual.error_text(f"Failed to checkout branch: {str(e)}")
        ctx.textual.text("")
        ctx.textual.end_step("error")
        return Error(f"Failed to checkout: {str(e)}")


__all__ = ["checkout_branch_step"]
