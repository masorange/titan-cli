"""
Fetch PR Threads Step

Fetches review comment threads for the selected PR.
Uses the same logic as the old workflow.
"""

from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error
from titan_cli.core.result import ClientSuccess, ClientError


def fetch_pr_threads_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Fetch all review comment threads and general comments for the selected PR.

    Requires (from ctx.data):
        review_pr_number (int): The PR number

    Outputs (saved to ctx.data):
        review_threads (List[UICommentThread]): All review threads

    Returns:
        Success (even if no threads), or Error if fetch fails
    """
    ctx.textual.begin_step("Fetch PR Threads")

    pr_number = ctx.data.get("review_pr_number")
    if not pr_number:
        ctx.textual.warning_text("No PR number found")
        ctx.textual.end_step("skip")
        return Success("No PR selected")

    if not ctx.github:
        return Error("GitHub client not available")

    # Fetch review threads and general comments (same as old workflow)
    with ctx.textual.loading("Fetching PR comments..."):
        threads_result = ctx.github.get_pr_review_threads(pr_number, include_resolved=False)
        general_result = ctx.github.get_pr_general_comments(pr_number)

    # Extract threads using pattern matching
    all_threads = []
    match threads_result:
        case ClientSuccess(data=threads):
            all_threads.extend(threads)
        case ClientError(error_message=err):
            ctx.textual.warning_text(f"Could not fetch review threads: {err}")
            return Error(f"Failed to fetch review threads: {err}")

    # Extract general comments using pattern matching
    match general_result:
        case ClientSuccess(data=general_comments):
            all_threads.extend(general_comments)
        case ClientError(error_message=err):
            ctx.textual.warning_text(f"Could not fetch general comments: {err}")
            return Error(f"Failed to fetch general comments: {err}")

    ctx.data["review_threads"] = all_threads

    ctx.textual.success_text(f"Found {len(all_threads)} thread(s)")
    ctx.textual.end_step("success")
    return Success(f"Fetched {len(all_threads)} comment thread(s)")
