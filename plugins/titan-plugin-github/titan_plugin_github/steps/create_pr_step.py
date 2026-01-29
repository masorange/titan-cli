# plugins/titan-plugin-github/titan_plugin_github/steps/create_pr_step.py
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.ui.tui.widgets import Panel
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
        pr_labels (list[str], optional): Labels to add to the PR. Defaults to None.

    Configuration (from ctx.github.config):
        auto_assign_prs (bool): If True, automatically assigns the PR to the current GitHub user.

    Outputs (saved to ctx.data):
        pr_number (int): The number of the created pull request.
        pr_url (str): The URL of the created pull request.

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
    # Allow overriding base branch from context, otherwise use git client config
    base = ctx.get("pr_base_branch") or ctx.git.main_branch
    head = ctx.get("pr_head_branch")
    is_draft = ctx.get("pr_is_draft", False)  # Default to not a draft
    labels = ctx.get("pr_labels")  # Optional labels

    # DEBUG: Save received body to temp file for inspection
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='_received_pr_body.md', delete=False) as f:
        f.write(body if body else "EMPTY")
        temp_file = f.name

    # Debug: Show what we're getting from context
    if ctx.textual:
        ctx.textual.text("", markup="dim")
        ctx.textual.text("=" * 80, markup="yellow")
        ctx.textual.text("DEBUG: PR Data from Context", markup="bold yellow")
        ctx.textual.text(f"  pr_title: {title}", markup="dim")
        ctx.textual.text(f"  pr_body length: {len(body) if body else 0} chars", markup="dim")
        ctx.textual.text(f"  pr_head_branch: {head}", markup="dim")
        ctx.textual.text(f"  base: {base}", markup="dim")
        ctx.textual.text(f"  labels: {labels}", markup="dim")
        ctx.textual.text(f"  🐛 Body saved to: {temp_file}", markup="yellow")
        ctx.textual.text("=" * 80, markup="yellow")
        ctx.textual.text("", markup="dim")
    elif ctx.ui:
        ctx.ui.text.info("DEBUG: PR Data from Context")
        ctx.ui.text.info(f"  pr_title: {title}")
        ctx.ui.text.info(f"  pr_body length: {len(body) if body else 0} chars")
        ctx.ui.text.info(f"  pr_head_branch: {head}")
        ctx.ui.text.info(f"  base: {base}")
        ctx.ui.text.info(f"  labels: {labels}")
        ctx.ui.text.info(f"  🐛 Body saved to: {temp_file}")

    if not all([title, base, head]):
        return Error(
            "Missing required context for creating a pull request: pr_title, pr_head_branch."
        )

    # 3. Determine assignees from context or auto-assign if enabled
    assignees = ctx.get("pr_assignees")  # First try to get from context
    if not assignees and ctx.github.config.auto_assign_prs:
        # Fallback to auto-assign from config
        try:
            current_user = ctx.github.get_current_user()
            assignees = [current_user]
        except GitHubAPIError as e:
            # Log warning but continue without assignee
            if ctx.textual:
                ctx.textual.text(f"Could not get current user for auto-assign: {e}", markup="yellow")
            elif ctx.ui:
                ctx.ui.text.body(f"Could not get current user for auto-assign: {e}", style="yellow")

    # 4. Call the client method with labels included
    try:
        pr = ctx.github.create_pull_request(
            title=title, body=body, base=base, head=head, draft=is_draft,
            assignees=assignees, labels=labels
        )

        pr_number = pr["number"]
        pr_url = pr["url"]

        # 5. Show success message with labels info
        if labels and ctx.textual:
            ctx.textual.text(f"✓ Labels added: {', '.join(labels)}", markup="green")
        elif labels and ctx.ui:
            ctx.ui.text.success(f"✓ Labels added: {', '.join(labels)}")

        if ctx.textual:
            ctx.textual.mount(
                Panel(
                    text=msg.GitHub.PR_CREATED.format(number=pr_number, url=pr_url),
                    panel_type="success"
                )
            )
        elif ctx.ui:
            ctx.ui.panel.print(
                msg.GitHub.PR_CREATED.format(number=pr_number, url=pr_url),
                panel_type="success"
            )

        # 6. Return Success with PR info
        return Success(
            "Pull request created successfully.",
            metadata={"pr_number": pr_number, "pr_url": pr_url},
        )
    except GitHubAPIError as e:
        return Error(f"Failed to create pull request: {e}")
    except Exception as e:
        return Error(
            f"An unexpected error occurred while creating the pull request: {e}"
        )
