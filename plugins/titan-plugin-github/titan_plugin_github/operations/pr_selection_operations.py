"""Operations for building PR selection option content."""

from titan_plugin_github.models.view import UIPullRequest


def build_pr_selection_title(pr: UIPullRequest, highlight_assigned: bool = False) -> str:
    """Build the title for a PR selection option."""
    prefix = "⭐ " if highlight_assigned else ""
    return f"{prefix}#{pr.number}: {pr.title}"


def build_pr_selection_description(
    pr: UIPullRequest,
    *,
    include_author: bool = False,
    include_checks: bool = False,
    include_review_status: bool = False,
) -> str:
    """Build the description for a PR selection option."""
    parts: list[str] = []

    if include_author:
        parts.append(f"by {pr.author_name}")

    parts.append(pr.branch_info)

    if include_checks and pr.checks_summary:
        parts.append(f"Checks: {pr.checks_summary}")

    if include_review_status and pr.review_status_summary:
        parts.append(f"Review: {pr.review_status_summary}")

    return " · ".join(parts)
