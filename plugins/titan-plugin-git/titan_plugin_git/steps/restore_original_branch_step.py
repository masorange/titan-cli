"""
Restore original branch and pop stashed changes.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_plugin_git.exceptions import GitError


def restore_original_branch_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Restore original branch and pop stashed changes.

    Returns the user to their original branch and restores any changes
    that were stashed at the beginning of the workflow.

    This step ALWAYS executes, even if the workflow failed.

    Inputs (from ctx.data):
        original_branch (str): Name of the branch to restore
        has_stashed_changes (bool): Whether to pop stashed changes

    Returns:
        Success: Branch restored and changes popped if needed
        Error: Git operation failed
    """
    if ctx.textual:
        ctx.textual.begin_step("Restore Original Branch")

    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    if not ctx.git:
        ctx.textual.error_text("Git client not available in context")
        ctx.textual.end_step("error")
        return Error("Git client not available in context")

    try:
        # Get original branch from context
        original_branch = ctx.get("original_branch")
        has_stashed_changes = ctx.get("has_stashed_changes", False)

        if not original_branch:
            ctx.textual.warning_text("No original branch to restore")
            ctx.textual.end_step("success")
            return Success("No branch to restore")

        ctx.textual.text("")
        ctx.textual.dim_text(f"Returning to: {original_branch}")

        # Checkout original branch
        try:
            ctx.git.checkout(original_branch)
            ctx.textual.success_text(f"✓ Checked out {original_branch}")
        except GitError as e:
            ctx.textual.error_text(f"Failed to checkout {original_branch}: {str(e)}")
            ctx.textual.end_step("error")
            return Error(f"Failed to checkout: {str(e)}")

        # Pop stashed changes if any
        if has_stashed_changes:
            ctx.textual.text("")
            ctx.textual.dim_text("Restoring stashed changes...")

            with ctx.textual.loading("Popping stashed changes..."):
                success = ctx.git.stash_pop()

            if not success:
                ctx.textual.warning_text("Failed to pop stash automatically")
                ctx.textual.dim_text("Run: git stash pop")
                # Don't fail the step, just warn
            else:
                ctx.textual.success_text("✓ Changes restored")

        ctx.textual.text("")
        ctx.textual.end_step("success")
        return Success(
            f"Restored to {original_branch}",
            metadata={
                "original_branch": original_branch,
                "stash_popped": has_stashed_changes
            }
        )

    except Exception as e:
        ctx.textual.text("")
        ctx.textual.error_text(f"Failed to restore original branch: {str(e)}")
        ctx.textual.dim_text("You may need to manually restore your branch:")
        if ctx.get("original_branch"):
            ctx.textual.dim_text(f"  git checkout {ctx.get('original_branch')}")
        if ctx.get("has_stashed_changes"):
            ctx.textual.dim_text("  git stash pop")
        ctx.textual.text("")
        ctx.textual.end_step("error")
        return Error(f"Failed to restore: {str(e)}")


__all__ = ["restore_original_branch_step"]
