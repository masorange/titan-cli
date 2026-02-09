# plugins/titan-plugin-git/titan_plugin_git/steps/remove_worktree_step.py
"""
Step to remove a git worktree.

Cleans up worktrees created by create_worktree step.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
import shutil
import os


def remove_worktree(ctx: WorkflowContext) -> WorkflowResult:
    """
    Remove a git worktree.

    This step removes a worktree and cleans up its directory.
    Should be used to clean up worktrees created by create_worktree step.

    Params:
        path: Path to the worktree to remove (required, or uses worktree_path from context)
        force: Force removal even if worktree has uncommitted changes (default: false)

    Example:
        ```yaml
        - name: "Cleanup Worktree"
          plugin: git
          step: remove_worktree
          params:
            path: "{worktree_path}"  # From previous create_worktree step
        ```
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Begin step
    ctx.textual.begin_step("Remove Worktree")

    try:
        # Get parameters
        worktree_path = ctx.get("path") or ctx.get("worktree_path")
        if not worktree_path:
            ctx.textual.error_text("Parameter 'path' is required (or worktree_path in context)")
            ctx.textual.end_step("error")
            return Error("Missing required parameter: path")

        # Default to force=True for cleanup (we want to remove even if dirty)
        force = ctx.get("force", True)

        # Check if path exists
        if not os.path.exists(worktree_path):
            ctx.textual.text("")
            ctx.textual.warning_text(f"Worktree path does not exist: {worktree_path}")
            ctx.textual.end_step("success")
            return Success("Worktree already removed")

        # Display info
        ctx.textual.text("")
        ctx.textual.primary_text(f"Removing worktree: {worktree_path}")

        # Remove worktree using git
        try:
            ctx.git.remove_worktree(path=worktree_path, force=force)
            ctx.textual.success_text("✓ Git worktree removed")
        except Exception as e:
            ctx.textual.warning_text(f"Git worktree removal failed: {str(e)}")
            ctx.textual.dim_text("Attempting manual cleanup...")

        # Also remove directory if it still exists
        if os.path.exists(worktree_path):
            try:
                shutil.rmtree(worktree_path)
                ctx.textual.success_text("✓ Directory cleaned up")
            except Exception as e:
                ctx.textual.text("")
                ctx.textual.error_text(f"Failed to remove directory: {str(e)}")
                ctx.textual.end_step("error")
                return Error(f"Failed to cleanup directory: {str(e)}")

        # Success
        ctx.textual.text("")
        ctx.textual.success_text("✓ Worktree removed successfully")
        ctx.textual.end_step("success")

        return Success(f"Worktree removed: {worktree_path}")

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()

        ctx.textual.text("")
        ctx.textual.error_text(f"Failed to remove worktree: {str(e)}")
        ctx.textual.text("")
        ctx.textual.dim_text("Traceback:")
        ctx.textual.dim_text(error_detail)

        ctx.textual.end_step("error")
        return Error(f"Failed to remove worktree: {str(e)}")
