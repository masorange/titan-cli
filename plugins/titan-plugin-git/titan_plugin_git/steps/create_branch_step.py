"""
Create a new Git branch.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError
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
        branches_result = ctx.git.get_branches()

        match branches_result:
            case ClientSuccess(data=all_branches):
                branch_names = [b.name for b in all_branches]
                branch_exists = check_branch_exists(new_branch, branch_names)
            case ClientError(error_message=err):
                ctx.textual.error_text(f"Failed to get branches: {err}")
                ctx.textual.end_step("error")
                return Error(f"Failed to get branches: {err}")

        # Delete if exists and requested using operations
        if should_delete_before_create(branch_exists, delete_if_exists):
            ctx.textual.text("")
            ctx.textual.warning_text(f"Branch {new_branch} exists, deleting...")

            # If we're on the branch, checkout another one first using operations
            current_branch_result = ctx.git.get_current_branch()

            match current_branch_result:
                case ClientSuccess(data=current_branch):
                    safe_target = determine_safe_checkout_target(
                        current_branch=current_branch,
                        branch_to_delete=new_branch,
                        main_branch=ctx.git.main_branch,
                        all_branches=branch_names
                    )

                    if safe_target:
                        checkout_result = ctx.git.checkout(safe_target)
                        match checkout_result:
                            case ClientSuccess():
                                ctx.textual.dim_text(f"Switched to {safe_target}")
                            case ClientError(error_message=err):
                                ctx.textual.error_text(f"Failed to checkout {safe_target}: {err}")
                                ctx.textual.end_step("error")
                                return Error(f"Cannot checkout {safe_target}: {err}")
                    elif current_branch == new_branch:
                        # Cannot delete current branch and no safe target available
                        ctx.textual.error_text(f"Cannot delete current branch {new_branch}")
                        ctx.textual.end_step("error")
                        return Error("Cannot delete current branch")

                    # Delete the branch
                    delete_result = ctx.git.safe_delete_branch(new_branch, force=True)
                    match delete_result:
                        case ClientSuccess():
                            ctx.textual.success_text(f"✓ Deleted existing branch {new_branch}")
                        case ClientError(error_message=err):
                            ctx.textual.error_text(f"Failed to delete {new_branch}: {err}")
                            ctx.textual.end_step("error")
                            return Error(f"Failed to delete branch: {err}")

                case ClientError(error_message=err):
                    ctx.textual.error_text(f"Failed to get current branch: {err}")
                    ctx.textual.end_step("error")
                    return Error(f"Failed to get current branch: {err}")

        elif branch_exists:
            ctx.textual.error_text(f"Branch {new_branch} already exists")
            ctx.textual.dim_text("Set 'delete_if_exists: true' to recreate it")
            ctx.textual.end_step("error")
            return Error(f"Branch {new_branch} already exists")

        # Create the branch
        ctx.textual.text("")
        create_result = ctx.git.create_branch(new_branch, start_point=start_point)
        match create_result:
            case ClientSuccess():
                ctx.textual.success_text(f"✓ Created branch {new_branch}")
            case ClientError(error_message=err):
                ctx.textual.error_text(f"Failed to create {new_branch}: {err}")
                ctx.textual.end_step("error")
                return Error(f"Failed to create branch: {err}")

        # Checkout if requested
        if checkout:
            checkout_result = ctx.git.checkout(new_branch)
            match checkout_result:
                case ClientSuccess():
                    ctx.textual.success_text(f"✓ Checked out {new_branch}")
                case ClientError(error_message=err):
                    ctx.textual.warning_text(f"Branch created but failed to checkout: {err}")

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
        import traceback
        tb = traceback.format_exc()
        ctx.textual.text("")
        ctx.textual.error_text(f"Failed to create branch: {str(e)}")
        ctx.textual.text("")
        ctx.textual.dim_text("Full traceback:")
        for line in tb.split('\n'):
            ctx.textual.dim_text(line)
        ctx.textual.end_step("error")
        return Error(f"Failed to create branch: {str(e)}")


__all__ = ["create_branch_step"]
