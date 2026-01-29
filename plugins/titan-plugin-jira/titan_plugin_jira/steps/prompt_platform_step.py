"""
Prompt user for mobile platform (iOS or Android)
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


def prompt_platform_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Prompt user to select mobile platform.

    Outputs (saved to ctx.data):
        platform (str): Selected platform ("iOS" or "Android")
        repository (str): Repository name based on platform

    Returns:
        Success: Platform selected
        Error: User cancelled

    Example usage in workflow:
        ```yaml
        - id: prompt_platform
          plugin: jira
          step: prompt_platform
        ```
    """
    if ctx.views:
        ctx.views.step_header(
            name="Select Platform",
            step_type="plugin",
            step_detail="jira.prompt_platform"
        )

    if not ctx.views:
        return Error("Views not available in context")

    # Show info about platforms
    if ctx.ui:
        ctx.ui.spacer.small()
        ctx.ui.text.subtitle("Available Platforms")
        ctx.ui.text.body("  iOS - ragnarok-ios repository", style="dim")
        ctx.ui.text.body("  Android - ragnarok-android repository", style="dim")
        ctx.ui.spacer.small()

    # Prompt for platform selection
    platform = ctx.views.prompts.ask_choice(
        question="Select platform",
        choices=["iOS", "Android"]
    )

    if not platform:
        return Error("Platform selection cancelled")

    # Map platform to repository
    repository_map = {
        "iOS": "ragnarok-ios",
        "Android": "ragnarok-android"
    }

    repository = repository_map.get(platform, "")

    # Show confirmation
    if ctx.ui:
        ctx.ui.spacer.small()
        ctx.ui.panel.print(
            f"Selected: {platform} ({repository})",
            panel_type="info"
        )
        ctx.ui.spacer.small()

    return Success(
        f"Platform set to: {platform}",
        metadata={
            "platform": platform,
            "repository": repository
        }
    )


__all__ = ["prompt_platform_step"]
