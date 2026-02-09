# plugins/titan-plugin-git/titan_plugin_git/steps/create_worktree_step.py
"""
Step to create a temporary git worktree.

This allows working on a different branch without changing the current working directory.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
import tempfile


def create_worktree(ctx: WorkflowContext) -> WorkflowResult:
    """
    Create a temporary git worktree from main branch.

    This step creates a worktree in a temporary directory and checks out
    the main branch. Useful for operating on a clean branch without
    affecting your current working directory.

    Params:
        path: Custom path for worktree (optional, defaults to temp directory)

    Output variables:
        worktree_path: Path to the created worktree
        worktree_branch: Branch checked out in the worktree (main branch)

    Example:
        ```yaml
        - name: "Create Worktree"
          plugin: git
          step: create_worktree
        ```
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Begin step
    ctx.textual.begin_step("Create Worktree")

    try:
        # Always use main branch from git config
        branch = ctx.git.main_branch

        custom_path = ctx.get("path")

        # Determine worktree path
        if custom_path:
            worktree_path = custom_path
        else:
            # Create temporary directory
            temp_dir = tempfile.mkdtemp(prefix="titan-worktree-")
            worktree_path = temp_dir

        # Display info
        ctx.textual.text("")
        ctx.textual.primary_text(f"Creating worktree at: {worktree_path}")
        ctx.textual.dim_text(f"Branch: {branch}")

        # Check if worktree already exists (by path or branch) and remove it
        existing_worktrees = ctx.git.list_worktrees()
        for wt in existing_worktrees:
            wt_path = wt.get("path")
            wt_branch = wt.get("branch")

            # Skip the main worktree (the actual repository)
            if not wt.get("detached") and wt_branch is None:
                continue

            # Remove if same path OR same branch (Git doesn't allow same branch in multiple worktrees)
            if wt_path == worktree_path or wt_branch == branch:
                ctx.textual.text("")
                ctx.textual.warning_text(f"Worktree already exists (path: {wt_path}, branch: {wt_branch})")
                ctx.textual.dim_text("Removing existing worktree...")
                try:
                    ctx.git.remove_worktree(path=wt_path, force=True)
                    ctx.textual.dim_text("✓ Removed existing worktree")
                except Exception as e:
                    ctx.textual.dim_text(f"Warning: Could not remove worktree: {e}")

        # Create worktree (never create branch, always checkout existing main)
        ctx.textual.text("")
        ctx.git.create_worktree(
            path=worktree_path,
            branch=branch,
            create_branch=False
        )

        # Success
        ctx.textual.text("")
        ctx.textual.success_text(f"✓ Created worktree at {worktree_path}")

        ctx.textual.text("")
        ctx.textual.end_step("success")

        # Store in workflow variables
        return Success(
            f"Worktree created at {worktree_path}",
            metadata={
                "worktree_path": worktree_path,
                "worktree_branch": branch,
                "base_branch": branch  # Also save as base_branch for PR creation
            }
        )

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()

        ctx.textual.text("")
        ctx.textual.error_text(f"Failed to create worktree: {str(e)}")
        ctx.textual.text("")
        ctx.textual.dim_text("Traceback:")
        ctx.textual.dim_text(error_detail)

        ctx.textual.end_step("error")
        return Error(f"Failed to create worktree: {str(e)}")
