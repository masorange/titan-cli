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
        project_key (str, optional): Project key (defaults to ECAPP)

    Outputs (saved to ctx.data):
        versions (list): List of unreleased version names
        versions_full (list): List of full unreleased version objects

    Returns:
        Success: Unreleased versions listed
        Error: Failed to fetch versions

    Example usage in workflow:
        ```yaml
        - id: list_versions
          plugin: jira
          step: list_versions
          params:
            project_key: "ECAPP"
        ```
    """
    if not ctx.jira:
        return Error("JIRA client not available in context")

    # Get project key (default to ECAPP)
    project_key = ctx.get("project_key", "ECAPP")

    # Textual TUI (new UI)
    if ctx.textual:
        from titan_cli.ui.tui.widgets import Panel

        # Show fetching message
        ctx.textual.text(f"Fetching versions for project: {project_key}", markup="dim")
        ctx.textual.text("")

        try:
            # Get project details which includes versions
            project = ctx.jira.get_project(project_key)
            versions = project.get("versions", [])

            if not versions:
                ctx.textual.mount(
                    Panel(
                        f"No versions found for project {project_key}",
                        panel_type="info"
                    )
                )
                return Success(
                    "No versions found",
                    metadata={
                        "versions": [],
                        "versions_full": []
                    }
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
            ctx.textual.mount(
                Panel(
                    f"Found {len(sorted_versions)} unreleased versions",
                    panel_type="success"
                )
            )

            # Show versions list
            ctx.textual.text("")
            ctx.textual.text("Unreleased Versions:", markup="bold cyan")
            ctx.textual.text("")

            for v in sorted_versions[:20]:  # Show first 20
                name = v.get("name", "")
                description = v.get("description", "")
                desc_text = f" - {description[:50]}" if description else ""
                ctx.textual.text(f"  • {name}{desc_text}", markup="cyan")

            if len(sorted_versions) > 20:
                ctx.textual.text(f"  ... and {len(sorted_versions) - 20} more", markup="dim")
            ctx.textual.text("")

            return Success(
                f"Found {len(sorted_versions)} unreleased versions",
                metadata={
                    "versions": version_names,
                    "versions_full": sorted_versions
                }
            )

        except JiraAPIError as e:
            error_msg = f"Failed to fetch versions: {e}"
            ctx.textual.mount(Panel(error_msg, panel_type="error"))
            return Error(error_msg)
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            error_msg = f"Unexpected error: {e}\n\nTraceback:\n{error_detail}"
            ctx.textual.mount(Panel(error_msg, panel_type="error"))
            return Error(error_msg)

    # Rich UI (legacy)
    if ctx.views:
        ctx.views.step_header(
            name="List Project Versions",
            step_type="plugin",
            step_detail="jira.list_versions"
        )

    if ctx.ui:
        ctx.ui.spacer.small()
        ctx.ui.text.subtitle(f"Fetching versions for project: {project_key}")
        ctx.ui.spacer.small()

    try:
        # Get project details which includes versions
        if ctx.ui:
            ctx.ui.text.info("Fetching project details...")

        project = ctx.jira.get_project(project_key)
        versions = project.get("versions", [])

        if not versions:
            if ctx.ui:
                ctx.ui.panel.print(
                    f"No versions found for project {project_key}",
                    panel_type="info"
                )
                ctx.ui.spacer.small()
            return Success(
                "No versions found",
                metadata={
                    "versions": [],
                    "versions_full": []
                }
            )

        # Filter only unreleased versions for release notes workflow
        unreleased_versions = [v for v in versions if not v.get("released", False)]

        # Sort unreleased by name descending (most recent first)
        unreleased_versions.sort(key=lambda v: v.get("name", ""), reverse=True)

        # Use only unreleased versions
        sorted_versions = unreleased_versions

        # Extract version names
        version_names = [v.get("name", "") for v in sorted_versions]

        # Show versions
        if ctx.ui:
            ctx.ui.panel.print(
                f"Found {len(sorted_versions)} unreleased versions",
                panel_type="success"
            )
            ctx.ui.spacer.small()

            # Show versions list
            ctx.ui.text.subtitle("Unreleased Versions:")
            ctx.ui.spacer.small()

            for v in sorted_versions[:20]:  # Show first 20
                name = v.get("name", "")
                description = v.get("description", "")
                desc_text = f" - {description[:50]}" if description else ""
                ctx.ui.text.body(f"  • {name}{desc_text}", style="cyan")

            if len(sorted_versions) > 20:
                ctx.ui.text.body(f"  ... and {len(sorted_versions) - 20} more", style="dim")
            ctx.ui.spacer.small()

        return Success(
            f"Found {len(sorted_versions)} unreleased versions",
            metadata={
                "versions": version_names,
                "versions_full": sorted_versions
            }
        )

    except JiraAPIError as e:
        error_msg = f"Failed to fetch versions: {e}"
        if ctx.ui:
            ctx.ui.panel.print(error_msg, panel_type="error")
        return Error(error_msg)
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        error_msg = f"Unexpected error: {e}\n\nTraceback:\n{error_detail}"
        if ctx.ui:
            ctx.ui.panel.print(error_msg, panel_type="error")
        return Error(error_msg)


__all__ = ["list_versions_step"]
