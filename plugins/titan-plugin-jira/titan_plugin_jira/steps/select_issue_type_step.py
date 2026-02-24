"""
Select Issue Type Step

Lists available issue types in the project and lets user select one.
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
)
from titan_plugin_jira.utils import validate_numeric_selection


def select_issue_type(ctx: WorkflowContext) -> WorkflowResult:
    """
    Select issue type for the new issue.

    Requires:
    - ctx.jira.project_key (from client config)

    Stores in:
    - ctx.data["issue_type"] = str (e.g., "Story", "Bug", "Task")
    - ctx.data["issue_type_id"] = str (e.g., "10001")

    Returns:
        WorkflowResult
    """
    ctx.textual.begin_step(StepTitles.ISSUE_TYPE)

    ctx.textual.markdown("## 🏷️ Issue Type")
    ctx.textual.text("")

    # Get project key from client
    project_key = ctx.jira.project_key
    if not project_key:
        ctx.textual.mount(Panel(ErrorMessages.NO_PROJECT_CONFIGURED, panel_type="error"))
        ctx.textual.end_step("error")
        return Error("no_default_project")

    ctx.textual.dim_text(InfoMessages.GETTING_ISSUE_TYPES.format(project=project_key))
    ctx.textual.text("")

    # Get issue types from Jira
    result = ctx.jira.get_issue_types(project_key)

    match result:
        case ClientSuccess(data=issue_types):
            if not issue_types:
                ctx.textual.mount(Panel(ErrorMessages.NO_ISSUE_TYPES_FOUND, panel_type="error"))
                ctx.textual.end_step("error")
                return Error("no_issue_types")

            # Filter out subtasks (we don't want to create subtasks directly)
            issue_types = [it for it in issue_types if not it.subtask]

            if not issue_types:
                ctx.textual.mount(Panel(ErrorMessages.ONLY_SUBTASKS_AVAILABLE, panel_type="error"))
                ctx.textual.end_step("error")
                return Error("only_subtasks")

            # Show table with issue types
            ctx.textual.primary_text(InfoMessages.AVAILABLE_ISSUE_TYPES)
            ctx.textual.text("")

            headers = [
                UserPrompts.HEADER_NUMBER,
                UserPrompts.HEADER_TYPE,
                UserPrompts.HEADER_DESCRIPTION,
            ]
            rows = []
            for i, it in enumerate(issue_types, 1):
                description = it.description or ""
                # Limit description length
                if len(description) > 60:
                    description = description[:57] + "..."
                rows.append([str(i), it.name, description])

            ctx.textual.mount(
                Table(headers=headers, rows=rows, title=UserPrompts.ISSUE_TYPES_TABLE_TITLE)
            )
            ctx.textual.text("")

            # Ask for selection
            selection = ctx.textual.ask_text(
                UserPrompts.SELECT_NUMBER.format(min=1, max=len(issue_types)), default=""
            )

            # Validate selection
            is_valid, index, error_code = validate_numeric_selection(selection, 1, len(issue_types))

            if not is_valid:
                ctx.textual.mount(
                    Panel(
                        ErrorMessages.INVALID_SELECTION.format(
                            selection=selection, min=1, max=len(issue_types)
                        ),
                        panel_type="error",
                    )
                )
                ctx.textual.end_step("error")
                return Error(f"invalid_selection_{error_code}")

            selected_type = issue_types[index]

            if not selected_type:
                ctx.textual.mount(Panel(ErrorMessages.SELECTED_TYPE_NOT_FOUND, panel_type="error"))
                ctx.textual.end_step("error")
                return Error("selected_type_not_found")

            # Store in context
            ctx.data["issue_type"] = selected_type.name
            ctx.data["issue_type_id"] = selected_type.id

            ctx.textual.success_text(SuccessMessages.TYPE_SELECTED.format(type=selected_type.name))
            ctx.textual.text("")

            ctx.textual.end_step("success")

            return Success(
                f"Issue type selected: {selected_type.name}",
                metadata={"issue_type": selected_type.name, "issue_type_id": selected_type.id},
            )

        case ClientError(error_message=err):
            ctx.textual.mount(
                Panel(ErrorMessages.FAILED_TO_GET_ISSUE_TYPES.format(error=err), panel_type="error")
            )
            ctx.textual.end_step("error")
            return Error(f"failed_to_get_issue_types")
