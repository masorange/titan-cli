"""
Save current branch and stash uncommitted changes.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def save_current_branch_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Save current branch and stash uncommitted changes.

    This allows the workflow to create release notes in a separate branch
    without affecting the user's current work.

    Outputs (saved to ctx.data):
        original_branch (str): Name of the branch the user was on
        has_stashed_changes (bool): Whether changes were stashed

    Returns:
        Success: Branch saved and changes stashed if needed
        Error: Git operation failed
    """
    if ctx.textual:
        ctx.textual.begin_step("Save Current Branch")

    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    if not ctx.git:
        ctx.textual.error_text("Git client not available in context")
        ctx.textual.end_step("error")
        return Error("Git client not available in context")

    try:
        # Get current branch
        current_branch = ctx.git.get_current_branch()
        ctx.set("original_branch", current_branch)

        ctx.textual.text("")
        ctx.textual.dim_text(f"Current branch: {current_branch}")

        # Check for uncommitted changes
        has_changes = ctx.git.has_uncommitted_changes()

        if has_changes:
            ctx.textual.dim_text("Uncommitted changes detected")
            ctx.textual.text("")

            # Stash changes
            with ctx.textual.loading("Stashing uncommitted changes..."):
                success = ctx.git.stash_push(message="titan-release-notes-workflow")

            if not success:
                ctx.textual.error_text("Failed to stash changes")
                ctx.textual.end_step("error")
                return Error("Failed to stash changes")

            ctx.set("has_stashed_changes", True)
            ctx.textual.success_text("✓ Changes stashed successfully")
        else:
            ctx.textual.dim_text("No uncommitted changes")
            ctx.set("has_stashed_changes", False)

        ctx.textual.text("")
        ctx.textual.end_step("success")
        return Success(
            f"Saved branch: {current_branch}",
            metadata={
                "original_branch": current_branch,
                "has_stashed_changes": has_changes
            }
        )

    except Exception as e:
        ctx.textual.text("")
        ctx.textual.error_text(f"Failed to save current branch: {str(e)}")
        ctx.textual.text("")
        ctx.textual.end_step("error")
        return Error(f"Failed to save current branch: {str(e)}")


__all__ = ["save_current_branch_step"]
