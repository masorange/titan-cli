"""
Search JIRA issues using a custom JQL query
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from ..exceptions import JiraAPIError
from ..messages import msg


def search_issues_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Search JIRA issues using a custom JQL query.

    Inputs (from ctx.data):
        jql (str): JQL query string (e.g., 'fixVersion = "26.4.0" AND project = ECAPP')
        max_results (int, optional): Maximum number of results (default: 100)

    Outputs (saved to ctx.data):
        issues (list): List of raw issue dictionaries from JIRA API
        issue_count (int): Number of issues found

    Returns:
        Success: Issues found
        Error: Search failed

    Example usage in workflow:
        ```yaml
        - id: search
          plugin: jira
          step: search_issues
          params:
            jql: 'fixVersion = "26.4.0" AND project = ECAPP ORDER BY key ASC'
            max_results: 100
        ```
    """
    if ctx.views:
        ctx.views.step_header(
            name="Search JIRA Issues",
            step_type="plugin",
            step_detail="jira.search_issues"
        )

    if not ctx.jira:
        if ctx.ui:
            ctx.ui.panel.print(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT, panel_type="error")
        return Error(msg.Plugin.CLIENT_NOT_AVAILABLE_IN_CONTEXT)

    # Get JQL query
    jql = ctx.get("jql")
    if not jql:
        error_msg = "JQL query is required (param: jql)"
        if ctx.ui:
            ctx.ui.panel.print(error_msg, panel_type="error")
        return Error(error_msg)

    # Get max results
    max_results = ctx.get("max_results", 100)

    if ctx.ui:
        ctx.ui.spacer.small()
        ctx.ui.text.subtitle("Executing JQL Query")
        ctx.ui.text.body(f"  {jql}", style="dim")
        ctx.ui.text.body(f"  Max results: {max_results}", style="dim")
        ctx.ui.spacer.small()

    try:
        # Execute search using JiraClient's search_tickets method
        if ctx.ui:
            ctx.ui.text.info("Searching JIRA...")

        # Search with all needed fields including custom field for brands
        tickets = ctx.jira.search_tickets(
            jql=jql,
            max_results=max_results,
            fields=[
                "key",
                "summary",
                "description",
                "status",
                "assignee",
                "priority",
                "issuetype",
                "customfield_11931",  # Affected brands field
            ]
        )

        # Extract raw issue data from tickets
        issues = [ticket.raw for ticket in tickets]

        if not issues:
            if ctx.ui:
                ctx.ui.panel.print(
                    "No issues found for the specified JQL query",
                    panel_type="info"
                )
                ctx.ui.spacer.small()
            return Success(
                "No issues found",
                metadata={
                    "issues": [],
                    "issue_count": 0
                }
            )

        # Show results
        if ctx.ui:
            ctx.ui.panel.print(
                f"Found {len(issues)} issues",
                panel_type="success"
            )
            ctx.ui.spacer.small()

            # Show brief summary
            ctx.ui.text.subtitle("Issues Retrieved:")
            for issue in issues[:10]:  # Show first 10
                key = issue.get("key", "N/A")
                summary = issue.get("fields", {}).get("summary", "No summary")
                ctx.ui.text.body(f"  • {key}: {summary[:60]}")

            if len(issues) > 10:
                ctx.ui.text.body(f"  ... and {len(issues) - 10} more", style="dim")

            ctx.ui.spacer.small()

        return Success(
            f"Found {len(issues)} issues",
            metadata={
                "issues": issues,
                "issue_count": len(issues)
            }
        )

    except JiraAPIError as e:
        error_msg = f"JIRA search failed: {e}"
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


__all__ = ["search_issues_step"]
