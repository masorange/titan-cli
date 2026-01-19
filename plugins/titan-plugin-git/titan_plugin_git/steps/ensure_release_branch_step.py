"""
Ensure we're on a release notes branch, creating it if necessary.
"""

import re
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def ensure_release_branch_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Ensure we're on a release notes branch for the specified version.

    If current branch is not release-notes/{version}:
    1. Checkout develop
    2. Pull latest changes
    3. Create new branch: release-notes/{version}
    4. Checkout new branch

    Pattern: release-notes/{fix_version}
    Example: release-notes/26.4.0

    Inputs (from ctx.data):
        fix_version (str): Version for release notes (e.g., "26.4.0")

    Outputs (saved to ctx.data):
        release_branch (str): Name of release notes branch
        branch_created (bool): True if new branch was created

    Returns:
        Success: Branch is ready
        Error: Git operation failed

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

    if ctx.ui:
        ctx.ui.spacer.small()
        ctx.ui.text.subtitle(f"Target branch: {release_branch}")
        ctx.ui.spacer.small()

    try:
        # Get current branch using GitClient
        current_branch = ctx.git.get_current_branch()

        if ctx.ui:
            ctx.ui.text.info(f"Current branch: {current_branch}")

        # Check if already on release notes branch
        if current_branch == release_branch:
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
                    "branch_created": False
                }
            )

        # Check if it's any release notes branch (different version)
        if re.match(r"^release-notes/\d+\.\d+\.\d+$", current_branch):
            if ctx.ui:
                ctx.ui.panel.print(
                    f"On different release notes branch: {current_branch}\n"
                    f"Switching to {release_branch}",
                    panel_type="info"
                )
                ctx.ui.spacer.small()

        # Not on correct release notes branch - create it
        if ctx.ui:
            ctx.ui.text.info("Creating new release notes branch from develop...")

        # 1. Checkout develop
        if ctx.ui:
            ctx.ui.text.body("  1. Checking out develop...", style="dim")
        ctx.git.checkout("develop")

        # 2. Pull latest changes
        if ctx.ui:
            ctx.ui.text.body("  2. Pulling latest changes...", style="dim")
        ctx.git.pull(branch="develop")

        # 3. Create new branch from develop
        if ctx.ui:
            ctx.ui.text.body(f"  3. Creating branch {release_branch}...", style="dim")
        ctx.git.create_branch(release_branch, start_point="develop")

        # 4. Checkout new branch
        if ctx.ui:
            ctx.ui.text.body(f"  4. Checking out {release_branch}...", style="dim")
        ctx.git.checkout(release_branch)

        if ctx.ui:
            ctx.ui.spacer.small()
            ctx.ui.panel.print(
                f"Created and switched to {release_branch}",
                panel_type="success"
            )
            ctx.ui.spacer.small()

        return Success(
            f"Created branch {release_branch}",
            metadata={
                "release_branch": release_branch,
                "branch_created": True
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
