"""
Ensure we're on a release notes branch, creating it if necessary.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def ensure_release_branch_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Ensure we're on a release notes branch for the specified version.

    If current branch is not release-notes/{version}:
    1. Create new branch: release-notes/{version} from CURRENT branch
    2. Checkout new branch

    Pattern: release-notes/{fix_version}
    Example: release-notes/26.4.0

    Inputs (from ctx.data):
        fix_version (str): Version for release notes (e.g., "26.4.0")

    Outputs (saved to ctx.data):
        release_branch (str): Name of release notes branch
        branch_created (bool): True if new branch was created
        source_branch (str): Branch from which release branch was created

    Returns:
        Success: Branch is ready
        Error: Git operation failed or on protected branch

    Example usage in workflow:
        ```yaml
        - id: ensure_branch
          plugin: git
          step: ensure_release_branch
          requires:
            - fix_version
        ```
    """
    if ctx.views:
        ctx.views.step_header(
            name="Ensure Release Notes Branch",
            step_type="plugin",
            step_detail="git.ensure_release_branch"
        )

    if not ctx.git:
        return Error("Git client not available in context")

    # Get version
    fix_version = ctx.get("fix_version")
    if not fix_version:
        return Error("fix_version is required")

    # Expected branch name
    release_branch = f"release-notes/{fix_version}"

    # Textual TUI
    if ctx.textual:
        ctx.textual.text("")
        ctx.textual.text(f"Target branch: {release_branch}", markup="bold")
        ctx.textual.text("")

    # Rich UI
    if ctx.ui:
        ctx.ui.spacer.small()
        ctx.ui.text.subtitle(f"Target branch: {release_branch}")
        ctx.ui.spacer.small()

    try:
        # Get current branch using GitClient
        current_branch = ctx.git.get_current_branch()

        # Note: It's OK to start from develop - we'll create a branch immediately
        # The safety check in commit step will prevent accidental commits to develop

        if ctx.textual:
            ctx.textual.text(f"Current branch: {current_branch}", markup="dim")

        if ctx.ui:
            ctx.ui.text.info(f"Current branch: {current_branch}")

        # Check if already on release notes branch
        if current_branch == release_branch:
            if ctx.textual:
                from titan_cli.ui.tui.widgets import Panel
                ctx.textual.mount(
                    Panel(f"Already on branch {release_branch}", panel_type="success")
                )
                ctx.textual.text("")

            if ctx.ui:
                ctx.ui.panel.print(
                    f"Already on branch {release_branch}",
                    panel_type="success"
                )
                ctx.ui.spacer.small()

            return Success(
                f"Already on {release_branch}",
                metadata={
                    "release_branch": release_branch,
                    "branch_created": False,
                    "source_branch": current_branch
                }
            )

        # Check if branch already exists locally
        all_branches = ctx.git.get_branches()
        branch_exists = release_branch in all_branches

        if branch_exists:
            # Branch exists, just checkout
            if ctx.textual:
                ctx.textual.text(f"Branch {release_branch} exists, switching to it...", markup="cyan")

            if ctx.ui:
                ctx.ui.text.info(f"Branch {release_branch} exists, switching to it...")

            ctx.git.checkout(release_branch)

            if ctx.textual:
                from titan_cli.ui.tui.widgets import Panel
                ctx.textual.mount(
                    Panel(f"Switched to existing branch {release_branch}", panel_type="success")
                )
                ctx.textual.text("")

            if ctx.ui:
                ctx.ui.panel.print(
                    f"Switched to existing branch {release_branch}",
                    panel_type="success"
                )

            return Success(
                f"Switched to existing {release_branch}",
                metadata={
                    "release_branch": release_branch,
                    "branch_created": False,
                    "source_branch": current_branch
                }
            )

        # Branch doesn't exist - create it from current branch
        if ctx.textual:
            ctx.textual.text(f"Creating branch {release_branch} from {current_branch}...", markup="cyan")

        if ctx.ui:
            ctx.ui.text.info(f"Creating branch {release_branch} from {current_branch}...")

        try:
            ctx.git.create_branch(release_branch, start_point=current_branch)
            ctx.git.checkout(release_branch)
        except Exception as e:
            # If branch already exists (race condition), just checkout
            if "already exists" in str(e).lower():
                if ctx.textual:
                    ctx.textual.text(f"Branch {release_branch} already exists, switching to it...", markup="yellow")
                if ctx.ui:
                    ctx.ui.text.body(f"Branch {release_branch} already exists, switching to it...", style="yellow")
                ctx.git.checkout(release_branch)
                branch_exists = True
            else:
                raise

        # Success message
        action = "Switched to existing" if branch_exists else f"Created from {current_branch} and switched to"
        if ctx.textual:
            from titan_cli.ui.tui.widgets import Panel
            ctx.textual.mount(
                Panel(f"{action} {release_branch}", panel_type="success")
            )
            ctx.textual.text("")

        if ctx.ui:
            ctx.ui.spacer.small()
            ctx.ui.panel.print(
                f"{action} {release_branch}",
                panel_type="success"
            )
            ctx.ui.spacer.small()

        return Success(
            f"{action} {release_branch}",
            metadata={
                "release_branch": release_branch,
                "branch_created": not branch_exists,
                "source_branch": current_branch
            }
        )

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        error_msg = f"Failed to ensure release branch: {e}\n\nTraceback:\n{error_detail}"
        if ctx.ui:
            ctx.ui.panel.print(error_msg, panel_type="error")
        return Error(error_msg)


__all__ = ["ensure_release_branch_step"]
