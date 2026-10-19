"""
Switch to another local branch, choosing it from the ones most recently used.

The step refuses to move while the working tree has modified or staged files:
those would travel to the other branch and quietly mix with its work. Untracked
files stay put wherever HEAD goes, so they never block the switch.
"""

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error, Skip, Exit
from titan_cli.ui.tui.widgets import OptionItem

from ..operations import switching_blocked_by

GIT_CLIENT_NOT_AVAILABLE = "Git client is not available in the workflow context."
TEXTUAL_NOT_AVAILABLE = "Textual UI context is not available for this step."
DIRTY_HINT = "Untracked files are fine - it is the modified and staged ones that would travel with you."
NO_BRANCHES = "No other local branch to switch to"
ASK_BRANCH = "Which branch do you want to switch to?"
USER_CANCELLED = "No branch selected"


def _describe(branch) -> str:
    """The dim line under a branch: when it was last committed to and where it pushes."""
    parts = []
    if branch.formatted_date:
        parts.append(f"last commit {branch.formatted_date}")
    if branch.upstream_info:
        parts.append(branch.upstream_info)
    return " · ".join(parts)


def switch_branch(ctx: WorkflowContext) -> WorkflowResult:
    """
    Switch to another local branch, with the most recently used offered first.

    Requires:
        ctx.git: An initialized GitClient.
        ctx.textual: The Textual UI context.

    Inputs (from ctx.data):
        branch (str, optional): Branch to switch to; asks when absent
        branch_limit (int, optional): How many branches to offer (default: 10)

    Outputs (saved to ctx.data):
        branch (str): Branch now checked out
        previous_branch (str): Branch left behind

    Returns:
        Success: Branch switched
        Skip: Already on that branch, or nothing was chosen
        Exit: The working tree has uncommitted changes, nothing was touched
        Error: Git client unavailable, or the branch could not be listed or checked out
    """
    if not ctx.textual:
        return Error(TEXTUAL_NOT_AVAILABLE)

    ctx.textual.begin_step("Switch Branch")

    if not ctx.git:
        ctx.textual.error_text(GIT_CLIENT_NOT_AVAILABLE)
        ctx.textual.end_step("error")
        return Error(GIT_CLIENT_NOT_AVAILABLE)

    match ctx.git.get_status():
        case ClientSuccess(data=status):
            pass
        case ClientError(error_message=err):
            message = f"Failed to read the working tree: {err}"
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
            return Error(message)

    blocked = switching_blocked_by(status)
    if blocked:
        message = f"Cannot switch branch: {blocked}"
        ctx.textual.warning_text(message)
        ctx.textual.dim_text(DIRTY_HINT)
        ctx.textual.end_step("skip")
        return Exit(message)

    current = status.branch
    target = (ctx.get("branch") or "").strip()

    match ctx.git.list_recent_branches(limit=int(ctx.get("branch_limit", 10) or 10)):
        case ClientSuccess(data=branches):
            pass
        case ClientError(error_message=err):
            message = f"Failed to list branches: {err}"
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
            return Error(message)

    if not target:
        others = [b for b in branches if not b.is_current]
        if not others:
            ctx.textual.dim_text(NO_BRANCHES)
            ctx.textual.end_step("skip")
            return Skip(NO_BRANCHES)

        target = ctx.textual.ask_option(
            ASK_BRANCH,
            [OptionItem(value=b.name, title=b.name, description=_describe(b)) for b in others],
        )
        if not target:
            ctx.textual.end_step("skip")
            return Skip(USER_CANCELLED)

    if target == current:
        message = f"Already on {target}"
        ctx.textual.dim_text(message)
        ctx.textual.end_step("skip")
        return Skip(message)

    ctx.textual.dim_text(f"Switching to {target}...")

    match ctx.git.checkout(target):
        case ClientSuccess():
            pass
        case ClientError(error_message=err):
            message = f"Failed to switch branch: {err}"
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
            return Error(message)

    ctx.textual.success_text(f"✓ Switched to {target}")
    ctx.textual.end_step("success")
    return Success(f"Switched to {target}", metadata={"branch": target, "previous_branch": current})
