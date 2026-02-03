# plugins/titan-plugin-github/titan_plugin_github/steps/create_pr_step.py
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from ..exceptions import GitHubAPIError
from ..messages import msg


def create_pr_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Creates a GitHub pull request using data from the workflow context.

    Requires:
        ctx.github: An initialized GitHubClient.
        ctx.git: An initialized GitClient.

    Inputs (from ctx.data):
        pr_title (str): The title of the pull request.
        pr_body (str, optional): The body/description of the pull request.
        pr_head_branch (str): The branch with the new changes.
        pr_is_draft (bool, optional): Whether to create the PR as a draft. Defaults to False.

    Configuration (from ctx.github.config):
        auto_assign_prs (bool): If True, automatically assigns the PR to the current GitHub user.

    Outputs (saved to ctx.data):
        pr_number (int): The number of the created pull request.
        pr_url (str): The URL of the created pull request.

    Returns:
        Success: If the PR is created successfully.
        Error: If any required context arguments are missing or if the API call fails.
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    # Begin step container
    ctx.textual.begin_step("Create Pull Request")

    # 1. Get GitHub client from context
    if not ctx.github:
        ctx.textual.error_text("GitHub client is not available in the workflow context.")
        ctx.textual.end_step("error")
        return Error("GitHub client is not available in the workflow context.")
    if not ctx.git:
        ctx.textual.error_text("Git client is not available in the workflow context.")
        ctx.textual.end_step("error")
        return Error("Git client is not available in the workflow context.")

    # 2. Get required data from context and client config
    title = ctx.get("pr_title")
    body = ctx.get("pr_body")
    base = ctx.git.main_branch  # Get base branch from git client config
    head = ctx.get("pr_head_branch")
    is_draft = ctx.get("pr_is_draft", False)  # Default to not a draft

    if not all([title, base, head]):
        ctx.textual.error_text("Missing required context for creating a pull request: pr_title, pr_head_branch.")
        ctx.textual.end_step("error")
        return Error(
            "Missing required context for creating a pull request: pr_title, pr_head_branch."
        )

    # 3. Determine assignees if auto-assign is enabled
    assignees = None
    if ctx.github.config.auto_assign_prs:
        try:
            current_user = ctx.github.get_current_user()
            assignees = [current_user]
        except GitHubAPIError as e:
            # Log warning but continue without assignee
            ctx.textual.warning_text(f"Could not get current user for auto-assign: {e}")

    # 4. Call the client method
    try:
        ctx.textual.dim_text(f"Creating pull request '{title}' from {head} to {base}...")
        pr = ctx.github.create_pull_request(
            title=title, body=body, base=base, head=head, draft=is_draft, assignees=assignees
        )
        ctx.textual.text("")  # spacing
        ctx.textual.success_text(msg.GitHub.PR_CREATED.format(number=pr["number"], url=pr["url"]))

        # 4. Return Success with PR info
        ctx.textual.end_step("success")
        return Success(
            "Pull request created successfully.",
            metadata={"pr_number": pr["number"], "pr_url": pr["url"]},
        )
    except GitHubAPIError as e:
        ctx.textual.error_text(f"Failed to create pull request: {e}")
        ctx.textual.end_step("error")
        return Error(f"Failed to create pull request: {e}")
    except Exception as e:
        ctx.textual.error_text(f"An unexpected error occurred while creating the pull request: {e}")
        ctx.textual.end_step("error")
        return Error(
            f"An unexpected error occurred while creating the pull request: {e}"
        )
