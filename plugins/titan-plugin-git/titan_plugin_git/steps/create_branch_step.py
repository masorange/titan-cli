"""
Create a new Git branch.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_plugin_git.exceptions import GitError
from ..operations import (
    check_branch_exists,
    determine_safe_checkout_target,
    should_delete_before_create,
)


def create_branch_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Create a new Git branch.

    Inputs (from ctx.data):
        new_branch (str): Name of the branch to create
        start_point (str, optional): Starting point for the branch (defaults to HEAD)
        delete_if_exists (bool, optional): Delete the branch if it already exists (default: False)
        checkout (bool, optional): Checkout the new branch after creation (default: True)

    Returns:
        Success: Branch created successfully
        Error: Git operation failed
    """
    if ctx.textual:
        ctx.textual.begin_step("Create Branch")

    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    if not ctx.git:
        ctx.textual.error_text("Git client not available in context")
        ctx.textual.end_step("error")
        return Error("Git client not available in context")

    try:
        # Get params from context
        new_branch = ctx.get("new_branch")
        if not new_branch:
            ctx.textual.error_text("No branch name specified")
            ctx.textual.dim_text("Set 'new_branch' in workflow params or previous step")
            ctx.textual.end_step("error")
            return Error("No branch name specified")

        start_point = ctx.get("start_point", "HEAD")
        delete_if_exists = ctx.get("delete_if_exists", False)
        checkout = ctx.get("checkout", True)

        ctx.textual.text("")
        ctx.textual.dim_text(f"Creating branch: {new_branch}")
        ctx.textual.dim_text(f"From: {start_point}")

        # Check if branch exists using operations
        all_branches = ctx.git.get_branches()
        branch_names = [b.name for b in all_branches]
        branch_exists = check_branch_exists(new_branch, branch_names)

        # Delete if exists and requested using operations
        if should_delete_before_create(branch_exists, delete_if_exists):
            ctx.textual.text("")
            ctx.textual.warning_text(f"Branch {new_branch} exists, deleting...")

            # If we're on the branch, checkout another one first using operations
            current_branch = ctx.git.get_current_branch()
            safe_target = determine_safe_checkout_target(
                current_branch=current_branch,
                branch_to_delete=new_branch,
                main_branch=ctx.git.main_branch,
                all_branches=branch_names
            )

            if safe_target:
                try:
                    ctx.git.checkout(safe_target)
                    ctx.textual.dim_text(f"Switched to {safe_target}")
                except GitError as e:
                    ctx.textual.error_text(f"Failed to checkout {safe_target}: {str(e)}")
                    ctx.textual.end_step("error")
                    return Error(f"Cannot checkout {safe_target}: {str(e)}")
            elif current_branch == new_branch:
                # Cannot delete current branch and no safe target available
                ctx.textual.error_text(f"Cannot delete current branch {new_branch}")
                ctx.textual.end_step("error")
                return Error("Cannot delete current branch")

            # Delete the branch
            try:
                ctx.git.safe_delete_branch(new_branch, force=True)
                ctx.textual.success_text(f"✓ Deleted existing branch {new_branch}")
            except GitError as e:
                ctx.textual.error_text(f"Failed to delete {new_branch}: {str(e)}")
                ctx.textual.end_step("error")
                return Error(f"Failed to delete branch: {str(e)}")

        elif branch_exists:
            ctx.textual.error_text(f"Branch {new_branch} already exists")
            ctx.textual.dim_text("Set 'delete_if_exists: true' to recreate it")
            ctx.textual.end_step("error")
            return Error(f"Branch {new_branch} already exists")

        # Create the branch
        ctx.textual.text("")
        try:
            ctx.git.create_branch(new_branch, start_point=start_point)
            ctx.textual.success_text(f"✓ Created branch {new_branch}")
        except GitError as e:
            ctx.textual.error_text(f"Failed to create {new_branch}: {str(e)}")
            ctx.textual.end_step("error")
            return Error(f"Failed to create branch: {str(e)}")

        # Checkout if requested
        if checkout:
            try:
                ctx.git.checkout(new_branch)
                ctx.textual.success_text(f"✓ Checked out {new_branch}")
            except GitError as e:
                ctx.textual.warning_text(f"Branch created but failed to checkout: {str(e)}")

        ctx.textual.text("")
        ctx.textual.end_step("success")
        return Success(
            f"Created branch {new_branch}",
            metadata={
                "new_branch": new_branch,
                "start_point": start_point,
                "checked_out": checkout
            }
        )

    except Exception as e:
        ctx.textual.text("")
        ctx.textual.error_text(f"Failed to create branch: {str(e)}")
        ctx.textual.text("")
        ctx.textual.end_step("error")
        return Error(f"Failed to create branch: {str(e)}")


__all__ = ["create_branch_step"]
