# plugins/titan-plugin-github/titan_plugin_github/steps/create_pr_step.py
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from ..exceptions import GitHubAPIError
from ..messages import msg


def create_pr_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Creates a GitHub pull request using data from the workflow context.

    If auto_assign_prs is enabled in plugin configuration, automatically assigns
    the PR to the current user. Assignment failures are non-blocking.

    Requires:
        ctx.github: An initialized GitHubClient.
        ctx.git: An initialized GitClient.

    Inputs (from ctx.data):
        pr_title (str): The title of the pull request.
        pr_body (str, optional): The body/description of the pull request.
        pr_head_branch (str): The branch with the new changes.
        pr_is_draft (bool, optional): Whether to create the PR as a draft. Defaults to False.

    Outputs (saved to ctx.data):
        pr_number (int): The number of the created pull request.
        pr_url (str): The URL of the created pull request.

    Configuration:
        auto_assign_prs (bool): If True, automatically assigns PR to creator.
                               Configured in .titan/config.toml under [plugins.github.config]

    Returns:
        Success: If the PR is created successfully.
        Error: If any required context arguments are missing or if the API call fails.
    """
    # 1. Get GitHub client from context
    if not ctx.github:
        return Error("GitHub client is not available in the workflow context.")
    if not ctx.git:
        return Error("Git client is not available in the workflow context.")

    # 2. Get required data from context and client config
    title = ctx.get("pr_title")
    body = ctx.get("pr_body")
    base = ctx.git.main_branch  # Get base branch from git client config
    head = ctx.get("pr_head_branch")
    is_draft = ctx.get("pr_is_draft", False)  # Default to not a draft

    if not all([title, base, head]):
        return Error(
            "Missing required context for creating a pull request: pr_title, pr_head_branch."
        )

    # 3. Call the client method
    try:
        pr = ctx.github.create_pull_request(
            title=title, body=body, base=base, head=head, draft=is_draft
        )
        ctx.ui.panel.print(
            msg.GitHub.PR_CREATED.format(number=pr["number"], url=pr["url"]),
            panel_type="success",
        )

        # 4. Auto-assign PR to creator if configured
        if ctx.github.config.auto_assign_prs:
            try:
                current_user = ctx.github.get_current_user()
                ctx.github.assign_pr(pr["number"], [current_user])
                ctx.ui.text.info(f"Assigned PR to {current_user}")
            except Exception as e:
                # Don't fail the workflow if assignment fails
                ctx.ui.text.warning(f"Could not auto-assign PR: {e}")

        # 5. Return Success with PR info
        return Success(
            "Pull request created successfully.",
            metadata={"pr_number": pr["number"], "pr_url": pr["url"]},
        )
    except GitHubAPIError as e:
        return Error(f"Failed to create pull request: {e}")
    except Exception as e:
        return Error(
            f"An unexpected error occurred while creating the pull request: {e}"
        )
