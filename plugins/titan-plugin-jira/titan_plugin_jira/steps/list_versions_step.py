"""
List available versions (fixVersions) for a JIRA project
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from ..exceptions import JiraAPIError


def list_versions_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    List unreleased versions for a JIRA project.

    Filters and returns only versions that are not yet released,
    sorted by name in descending order (most recent first).

    Inputs (from ctx.data):
        project_key (str, optional): Project key. If not provided, uses default_project from JIRA plugin config.

    Outputs (saved to ctx.data):
        versions (list): List of unreleased version names
        versions_full (list): List of full unreleased version objects

    Returns:
        Success: Unreleased versions listed
        Error: Failed to fetch versions or project_key not configured

    Example usage in workflow:
        ```yaml
        - id: list_versions
          plugin: jira
          step: list_versions
          params:
            project_key: "MYPROJECT"
        ```
    """
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    if not ctx.jira:
        return Error("JIRA client not available in context")

    # Begin step container
    ctx.textual.begin_step("List Project Versions")

    # Get project key from context or fall back to default_project from JIRA client
    project_key = ctx.get("project_key")
    if not project_key:
        # Try to use default project from JIRA client config
        if hasattr(ctx.jira, 'project_key') and ctx.jira.project_key:
            project_key = ctx.jira.project_key
            ctx.textual.dim_text(f"Using default project from JIRA config: {project_key}")
        else:
            ctx.textual.error_text("project_key is required but not provided")
            ctx.textual.dim_text("Set project_key in workflow params or configure default_project in JIRA plugin")
            ctx.textual.end_step("error")
            return Error("project_key is required. Provide it in workflow params or configure default_project in JIRA plugin.")

    # Show fetching message
    ctx.textual.dim_text(f"Fetching versions for project: {project_key}")
    ctx.textual.text("")

    try:
        # Get project details which includes versions
        project = ctx.jira.get_project(project_key)
        versions = project.get("versions", [])

        if not versions:
            ctx.textual.panel(
                f"No versions found for project {project_key}", panel_type="info"
            )
            ctx.textual.end_step("skip")
            return Success(
                "No versions found", metadata={"versions": [], "versions_full": []}
            )

        # Filter only unreleased versions for release notes workflow
        unreleased_versions = [v for v in versions if not v.get("released", False)]

        # Sort unreleased by name descending (most recent first)
        unreleased_versions.sort(key=lambda v: v.get("name", ""), reverse=True)

        # Use only unreleased versions
        sorted_versions = unreleased_versions

        # Extract version names
        version_names = [v.get("name", "") for v in sorted_versions]

        # Show success panel
        ctx.textual.text("")
        ctx.textual.panel(
            f"Found {len(sorted_versions)} unreleased versions",
            panel_type="success",
        )

        # Show versions list
        ctx.textual.text("")
        ctx.textual.bold_primary_text("Unreleased Versions:")
        ctx.textual.text("")

        for v in sorted_versions[:20]:  # Show first 20
            name = v.get("name", "")
            description = v.get("description", "")
            desc_text = f" - {description[:50]}" if description else ""
            ctx.textual.primary_text(f"  • {name}{desc_text}")

        if len(sorted_versions) > 20:
            ctx.textual.dim_text(
                f"  ... and {len(sorted_versions) - 20} more"
            )
        ctx.textual.text("")

        ctx.textual.end_step("success")
        return Success(
            f"Found {len(sorted_versions)} unreleased versions",
            metadata={"versions": version_names, "versions_full": sorted_versions},
        )

    except JiraAPIError as e:
        error_msg = f"Failed to fetch versions: {e}"
        ctx.textual.panel(error_msg, panel_type="error")
        ctx.textual.end_step("error")
        return Error(error_msg)
    except Exception as e:
        import traceback

        error_detail = traceback.format_exc()
        error_msg = f"Unexpected error: {e}\n\nTraceback:\n{error_detail}"
        ctx.textual.panel(error_msg, panel_type="error")
        ctx.textual.end_step("error")
        return Error(error_msg)


__all__ = ["list_versions_step"]
