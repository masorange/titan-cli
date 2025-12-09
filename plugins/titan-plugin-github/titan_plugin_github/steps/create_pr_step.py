# plugins/titan-plugin-github/titan_plugin_github/steps/create_pr_step.py
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip
from ..exceptions import GitHubAPIError

def create_pr_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Creates a GitHub pull request using data from the workflow context.
    Skips if no new commit was created in the workflow.

    Requires:
        ctx.github: An initialized GitHubClient.

    Inputs (from ctx.data):
        commit_hash (str, optional): The hash of the created commit. If not present, the step is skipped.
        pr_title (str): The title of the pull request.
        pr_body (str, optional): The body/description of the pull request.
        pr_head_branch (str): The branch with the new changes.
        pr_is_draft (bool, optional): Whether to create the PR as a draft. Defaults to False.

    Outputs (saved to ctx.data):
        pr_number (int): The number of the created pull request.
        pr_url (str): The URL of the created pull request.

    Returns:
        Success: If the PR is created successfully.
        Error: If any required context arguments are missing or if the API call fails.
        Skip: If no commit was made.
    """
    # 1. Skip if no commit was made
    if not ctx.get('commit_hash'):
        return Skip("No new commit was created, skipping pull request creation.")

    # 2. Get GitHub client from context
    if not ctx.github:
        return Error("GitHub client is not available in the workflow context.")
    if not ctx.git:
        return Error("Git client is not available in the workflow context.")

    # 2. Get required data from context and client config
    title = ctx.get("pr_title")
    body = ctx.get("pr_body")
    base = ctx.git.main_branch # Get base branch from git client config
    head = ctx.get("pr_head_branch")
    is_draft = ctx.get("pr_is_draft", False) # Default to not a draft

    if not all([title, base, head]):
        return Error("Missing required context for creating a pull request: pr_title, pr_head_branch.")

    # 3. Call the client method
    try:
        ctx.ui.text.info(f"Creating pull request: '{title}'")
        pr = ctx.github.create_pull_request(
            title=title,
            body=body,
            base=base,
            head=head,
            draft=is_draft
        )
        ctx.ui.text.success(f"Successfully created PR #{pr['number']}: {pr['url']}")

        # 4. Return Success with PR info
        return Success(
            f"Pull request #{pr['number']} created.",
            metadata={
                "pr_number": pr["number"],
                "pr_url": pr["url"]
            }
        )
    except GitHubAPIError as e:
        return Error(f"Failed to create pull request: {e}")
    except Exception as e:
        return Error(f"An unexpected error occurred while creating the pull request: {e}")
