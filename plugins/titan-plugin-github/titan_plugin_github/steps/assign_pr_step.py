# plugins/titan-plugin-github/titan_plugin_github/steps/assign_pr_step.py
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from ..exceptions import GitHubAPIError


def assign_pr_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Assigns users to a GitHub pull request.

    Requires:
        ctx.github: An initialized GitHubClient.

    Inputs (from ctx.data):
        pr_number (int): The PR number to assign.
        assignees (list[str], optional): List of GitHub usernames to assign.
                                        If not provided, assigns to current user (@me).

    Returns:
        Success: If the PR is assigned successfully.
        Error: If any required context arguments are missing or if the API call fails.

    Examples:
        # Auto-assign to current user
        ctx.data["pr_number"] = 123
        # assignees not provided, defaults to current user

        # Assign to specific users
        ctx.data["pr_number"] = 123
        ctx.data["assignees"] = ["user1", "user2"]
    """
    # 1. Get GitHub client from context
    if not ctx.github:
        return Error("GitHub client is not available in the workflow context.")

    # 2. Get required data from context
    pr_number = ctx.get("pr_number")
    if not pr_number:
        return Error("Missing required context: pr_number")

    # 3. Get assignees (default to current user)
    assignees = ctx.get("assignees")
    if not assignees:
        try:
            current_user = ctx.github.get_current_user()
            assignees = [current_user]
        except Exception as e:
            return Error(f"Failed to get current user: {e}")

    # 4. Assign the PR
    try:
        ctx.github.assign_pr(pr_number, assignees)

        assignee_list = ", ".join(assignees)
        ctx.ui.text.success(f"Assigned PR #{pr_number} to: {assignee_list}")

        return Success(
            f"Successfully assigned PR #{pr_number}",
            metadata={"pr_number": pr_number, "assignees": assignees},
        )

    except GitHubAPIError as e:
        return Error(f"Failed to assign PR: {e}")
    except Exception as e:
        return Error(f"An unexpected error occurred while assigning PR: {e}")
