"""Reusable workflow steps for GitHub pull request operations."""

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..messages import msg


def get_pull_request_step(ctx: WorkflowContext) -> WorkflowResult:
    """Fetch a pull request and store it in workflow context."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Fetch Pull Request")

    if not ctx.github:
        ctx.textual.error_text("GitHub client not available")
        ctx.textual.end_step("error")
        return Error("GitHub client not available")

    pr_number = ctx.get("pr_number")
    if not pr_number:
        ctx.textual.error_text("No PR number in context")
        ctx.textual.end_step("error")
        return Error("No PR number in context")

    with ctx.textual.loading(f"Fetching PR #{pr_number}..."):
        result = ctx.github.get_pull_request(int(pr_number))

    match result:
        case ClientSuccess(data=pr_info):
            ctx.textual.success_text(f"PR #{pr_info.number}: {pr_info.title}")
            ctx.textual.end_step("success")
            return Success(
                f"Fetched PR #{pr_info.number}",
                metadata={"pr_info": pr_info},
            )
        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed to fetch PR: {err}")
            ctx.textual.end_step("error")
            return Error(f"Failed to fetch PR: {err}")


def merge_pull_request_step(ctx: WorkflowContext) -> WorkflowResult:
    """Merge a pull request using the configured GitHub client."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Merge Pull Request")

    if not ctx.github:
        ctx.textual.error_text("GitHub client not available")
        ctx.textual.end_step("error")
        return Error("GitHub client not available")

    pr_number = ctx.get("pr_number")
    if not pr_number:
        ctx.textual.error_text("No PR number in context")
        ctx.textual.end_step("error")
        return Error("No PR number in context")

    merge_method = ctx.get("merge_method", "squash")
    commit_title = ctx.get("commit_title")
    commit_message = ctx.get("commit_message")

    with ctx.textual.loading(f"Merging PR #{pr_number} with {merge_method}..."):
        result = ctx.github.merge_pr(
            int(pr_number),
            merge_method=merge_method,
            commit_title=commit_title,
            commit_message=commit_message,
        )

    match result:
        case ClientSuccess(data=merge_result):
            if not merge_result.merged:
                ctx.textual.error_text(f"Failed to merge PR #{pr_number}: {merge_result.message}")
                ctx.textual.end_step("error")
                return Error(f"Failed to merge PR #{pr_number}: {merge_result.message}")

            ctx.textual.success_text(msg.GitHub.PR_MERGED.format(number=pr_number))
            ctx.textual.end_step("success")
            return Success(
                f"Merged PR #{pr_number}",
                metadata={"merge_result": merge_result},
            )
        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed to merge PR: {err}")
            ctx.textual.end_step("error")
            return Error(f"Failed to merge PR: {err}")


def verify_pull_request_state_step(ctx: WorkflowContext) -> WorkflowResult:
    """Verify a pull request is currently in the expected state."""
    if not ctx.textual:
        return Error("Textual UI context is not available for this step.")

    ctx.textual.begin_step("Verify Pull Request State")

    if not ctx.github:
        ctx.textual.error_text("GitHub client not available")
        ctx.textual.end_step("error")
        return Error("GitHub client not available")

    pr_number = ctx.get("pr_number")
    if not pr_number:
        ctx.textual.error_text("No PR number in context")
        ctx.textual.end_step("error")
        return Error("No PR number in context")

    expected_state = ctx.get("expected_state")
    if not expected_state:
        ctx.textual.error_text("No expected PR state in context")
        ctx.textual.end_step("error")
        return Error("No expected PR state in context")

    expected_state = str(expected_state).upper()

    with ctx.textual.loading(f"Verifying PR #{pr_number} state..."):
        result = ctx.github.get_pull_request(int(pr_number))

    match result:
        case ClientSuccess(data=pr_info):
            actual_state = str(pr_info.state).upper()
            if actual_state != expected_state:
                ctx.textual.error_text(
                    f"PR #{pr_number} is {actual_state}, expected {expected_state}"
                )
                ctx.textual.end_step("error")
                return Error(
                    f"PR #{pr_number} state mismatch: expected {expected_state}, got {actual_state}"
                )

            ctx.textual.success_text(f"PR #{pr_number} is {actual_state}")
            ctx.textual.end_step("success")
            return Success(
                f"Verified PR #{pr_number} is {actual_state}",
                metadata={"verified_pr_info": pr_info},
            )
        case ClientError(error_message=err):
            ctx.textual.error_text(f"Failed to verify PR state: {err}")
            ctx.textual.end_step("error")
            return Error(f"Failed to verify PR state: {err}")


__all__ = [
    "get_pull_request_step",
    "merge_pull_request_step",
    "verify_pull_request_state_step",
]
