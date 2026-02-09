# plugins/titan-plugin-git/titan_plugin_git/steps/worktree_command_step.py
"""
Step to execute git commands in a worktree.

Allows committing, pushing, and other git operations in a worktree.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
import subprocess


def worktree_commit(ctx: WorkflowContext) -> WorkflowResult:
    """
    Create a commit in a worktree.

    Params:
        worktree_path: Path to the worktree (required, or uses worktree_path from context)
        message: Commit message (required)
        add_all: Stage all changes before committing (default: true)

    Example:
        ```yaml
        - name: "Commit in Worktree"
          plugin: git
          step: worktree_commit
          params:
            worktree_path: "{worktree_path}"
            message: "chore: add release notes"
            add_all: true
        ```
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Commit in Worktree")

    try:
        # Get parameters
        worktree_path = ctx.get("worktree_path")
        if not worktree_path:
            ctx.textual.error_text("Parameter 'worktree_path' is required")
            ctx.textual.end_step("error")
            return Error("Missing required parameter: worktree_path")

        message = ctx.get("message") or ctx.get("commit_message")
        if not message:
            ctx.textual.error_text("Parameter 'message' is required")
            ctx.textual.end_step("error")
            return Error("Missing required parameter: message")

        add_all = ctx.get("add_all", True)

        # Display info
        ctx.textual.text("")
        ctx.textual.dim_text(f"Worktree: {worktree_path}")
        ctx.textual.primary_text(f"Message: {message}")

        # Stage files if requested
        if add_all:
            ctx.textual.text("")
            ctx.textual.primary_text("Staging all changes...")
            ctx.git.run_in_worktree(worktree_path, ["git", "add", "--all"])

        # Create commit
        ctx.textual.text("")
        ctx.textual.primary_text("Creating commit...")
        ctx.git.run_in_worktree(worktree_path, ["git", "commit", "-m", message])

        # Success
        ctx.textual.text("")
        ctx.textual.success_text("✓ Commit created in worktree")

        ctx.textual.end_step("success")
        return Success("Commit created in worktree")

    except subprocess.CalledProcessError as e:
        # stderr is already a string (text=True in subprocess.run)
        error_msg = e.stderr if e.stderr else str(e)
        ctx.textual.text("")
        ctx.textual.error_text(f"Commit failed: {error_msg}")
        ctx.textual.end_step("error")
        return Error(f"Commit failed: {error_msg}")

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()

        ctx.textual.text("")
        ctx.textual.error_text(f"Failed to commit: {str(e)}")
        ctx.textual.text("")
        ctx.textual.dim_text("Traceback:")
        ctx.textual.dim_text(error_detail)

        ctx.textual.end_step("error")
        return Error(f"Failed to commit: {str(e)}")


def worktree_push(ctx: WorkflowContext) -> WorkflowResult:
    """
    Push from a worktree.

    Params:
        worktree_path: Path to the worktree (required, or uses worktree_path from context)
        remote: Remote to push to (default: origin)
        branch: Branch to push (optional, pushes current branch if not specified)
        set_upstream: Set upstream tracking (default: true)

    Example:
        ```yaml
        - name: "Push from Worktree"
          plugin: git
          step: worktree_push
          params:
            worktree_path: "{worktree_path}"
            set_upstream: true
        ```
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Push from Worktree")

    try:
        # Get parameters
        worktree_path = ctx.get("worktree_path")
        if not worktree_path:
            ctx.textual.error_text("Parameter 'worktree_path' is required")
            ctx.textual.end_step("error")
            return Error("Missing required parameter: worktree_path")

        remote = ctx.get("remote", "origin")
        branch = ctx.get("branch")
        set_upstream = ctx.get("set_upstream", True)

        # Build push command
        push_args = ["git", "push"]

        if set_upstream:
            push_args.append("-u")

        push_args.append(remote)

        if branch:
            push_args.append(branch)

        # Display info
        ctx.textual.text("")
        ctx.textual.dim_text(f"Worktree: {worktree_path}")
        ctx.textual.primary_text(f"Remote: {remote}")
        if branch:
            ctx.textual.dim_text(f"Branch: {branch}")

        # Push
        ctx.textual.text("")
        ctx.textual.primary_text("Pushing to remote...")
        ctx.git.run_in_worktree(worktree_path, push_args)

        # Success
        ctx.textual.text("")
        ctx.textual.success_text(f"✓ Pushed to {remote}")

        ctx.textual.end_step("success")
        return Success(f"Pushed to {remote}")

    except subprocess.CalledProcessError as e:
        # stderr is already a string (text=True in subprocess.run)
        error_msg = e.stderr if e.stderr else str(e)
        ctx.textual.text("")
        ctx.textual.error_text(f"Push failed: {error_msg}")
        ctx.textual.end_step("error")
        return Error(f"Push failed: {error_msg}")

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()

        ctx.textual.text("")
        ctx.textual.error_text(f"Failed to push: {str(e)}")
        ctx.textual.text("")
        ctx.textual.dim_text("Traceback:")
        ctx.textual.dim_text(error_detail)

        ctx.textual.end_step("error")
        return Error(f"Failed to push: {str(e)}")
