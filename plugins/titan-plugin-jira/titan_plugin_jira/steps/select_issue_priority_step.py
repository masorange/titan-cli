"""
Select Issue Priority Step

Lists available priorities from Jira and lets user select one.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError
from titan_cli.ui.tui.widgets import Panel, Table
from titan_plugin_jira.constants import (
    StepTitles,
    UserPrompts,
    ErrorMessages,
    SuccessMessages,
    InfoMessages,
    DEFAULT_PRIORITIES,
)
from titan_plugin_jira.utils import validate_numeric_selection


def select_issue_priority(ctx: WorkflowContext) -> WorkflowResult:
    """
    Select priority for the new issue from available priorities in Jira.

    Stores in:
    - ctx.data["priority"] = str (e.g., "Medium", "High", "Low")

    Returns:
        WorkflowResult
    """
    ctx.textual.begin_step(StepTitles.PRIORITY)

    ctx.textual.markdown("## 🔥 Priority")
    ctx.textual.text("")

    # Verify Jira client is available
    if not ctx.jira:
        ctx.textual.mount(Panel(ErrorMessages.JIRA_CLIENT_UNAVAILABLE, panel_type="error"))
        ctx.textual.end_step("error")
        return Error("jira_client_unavailable")

    ctx.textual.dim_text(InfoMessages.GETTING_PRIORITIES)
    ctx.textual.text("")

    # Get priorities from Jira
    priorities = None
    try:
        result = ctx.jira.get_priorities()
    except Exception as e:
        # Fallback to default priorities on any exception
        ctx.textual.mount(
            Panel(
                ErrorMessages.UNEXPECTED_ERROR_PRIORITIES.format(error=str(e)),
                panel_type="warning",
            )
        )
        result = ClientError(error_message=str(e), error_code="UNEXPECTED_ERROR")

    match result:
        case ClientSuccess(data=fetched_priorities):
            if not fetched_priorities:
                # Fallback to standard priorities if none found
                ctx.textual.mount(
                    Panel(
                        f"{ErrorMessages.NO_PRIORITIES_FOUND}\n\n{InfoMessages.USING_STANDARD_PRIORITIES}",
                        panel_type="warning",
                    )
                )
                priorities = DEFAULT_PRIORITIES
            else:
                priorities = fetched_priorities

        case ClientError(error_message=err):
            ctx.textual.mount(
                Panel(
                    f"{ErrorMessages.FAILED_TO_GET_PRIORITIES.format(error=err)}\n\n{InfoMessages.USING_STANDARD_PRIORITIES}",
                    panel_type="warning",
                )
            )
            priorities = DEFAULT_PRIORITIES

    # Show table and get selection (common logic)
    selected_priority = _show_priorities_and_select(ctx, priorities)

    if not selected_priority:
        ctx.textual.end_step("error")
        return Error("invalid_priority_selection")

    # Store in context
    ctx.data["priority"] = selected_priority

    ctx.textual.success_text(SuccessMessages.PRIORITY_SELECTED.format(priority=selected_priority))
    ctx.textual.text("")

    ctx.textual.end_step("success")

    return Success(
        f"Priority selected: {selected_priority}",
        metadata={"priority": selected_priority},
    )


def _show_priorities_and_select(ctx: WorkflowContext, priorities: list) -> str | None:
    """
    Show priorities table and get user selection.

    Args:
        ctx: Workflow context
        priorities: List of UIPriority models

    Returns:
        Selected priority name, or None if invalid selection
    """
    # Show table with priorities
    ctx.textual.primary_text(InfoMessages.AVAILABLE_PRIORITIES)
    ctx.textual.text("")

    headers = [UserPrompts.HEADER_NUMBER, UserPrompts.HEADER_PRIORITY]
    rows = []
    for i, priority in enumerate(priorities, 1):
        rows.append([str(i), priority.label])  # Pre-formatted with icon

    ctx.textual.mount(Table(headers=headers, rows=rows, title=UserPrompts.PRIORITIES_TABLE_TITLE))
    ctx.textual.text("")

    # Ask for selection
    selection = ctx.textual.ask_text(
        UserPrompts.SELECT_NUMBER.format(min=1, max=len(priorities)), default=""
    )

    # Validate selection
    is_valid, index, error_code = validate_numeric_selection(selection, 1, len(priorities))

    if not is_valid:
        ctx.textual.mount(
            Panel(
                ErrorMessages.INVALID_SELECTION.format(
                    selection=selection, min=1, max=len(priorities)
                ),
                panel_type="error",
            )
        )
        return None

    return priorities[index].name
