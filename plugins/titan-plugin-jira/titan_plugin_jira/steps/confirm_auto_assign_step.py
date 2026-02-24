"""
Confirm Auto Assign Step

Asks user if they want to auto-assign the issue to themselves.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success
from titan_cli.core.result import ClientSuccess, ClientError
from titan_cli.ui.tui.widgets import Panel
from titan_plugin_jira.constants import (
    StepTitles,
    UserPrompts,
    ErrorMessages,
    SuccessMessages,
    InfoMessages,
)


def confirm_auto_assign(ctx: WorkflowContext) -> WorkflowResult:
    """
    Ask if user wants to auto-assign the issue.

    Stores in:
    - ctx.data["auto_assign"] = bool
    - ctx.data["assignee_id"] = str (if auto_assign is True)

    Returns:
        WorkflowResult
    """
    ctx.textual.begin_step(StepTitles.ASSIGNMENT)

    ctx.textual.markdown("## 👤 Assignment")
    ctx.textual.text("")

    # Get current user
    user_result = ctx.jira.get_current_user()

    match user_result:
        case ClientSuccess(data=user_data):
            display_name = user_data.get("displayName", "Unknown")
            account_id = user_data.get("accountId")

            ctx.textual.dim_text(InfoMessages.CURRENT_USER_LABEL.format(user=display_name))
            ctx.textual.text("")

            # Ask if want to auto-assign
            auto_assign = ctx.textual.ask_confirm(UserPrompts.WANT_TO_ASSIGN, default=True)

            ctx.data["auto_assign"] = auto_assign

            if auto_assign and account_id:
                ctx.data["assignee_id"] = account_id
                ctx.textual.success_text(
                    SuccessMessages.WILL_ASSIGN_TO.format(user=display_name)
                )
            else:
                ctx.data["assignee_id"] = None
                ctx.textual.dim_text(InfoMessages.WILL_REMAIN_UNASSIGNED)

        case ClientError(error_message=err):
            ctx.textual.mount(
                Panel(
                    ErrorMessages.FAILED_TO_GET_CURRENT_USER.format(error=err),
                    panel_type="warning",
                )
            )
            ctx.data["auto_assign"] = False
            ctx.data["assignee_id"] = None

    ctx.textual.text("")
    ctx.textual.end_step("success")

    return Success(
        f"Auto-assign: {ctx.data['auto_assign']}",
        metadata={"auto_assign": ctx.data["auto_assign"]},
    )
