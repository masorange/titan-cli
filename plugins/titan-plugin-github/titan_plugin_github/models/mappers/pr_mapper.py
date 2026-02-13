# plugins/titan-plugin-github/titan_plugin_github/models/mappers/pr_mapper.py
"""
Pull Request Mappers

Converts network models (REST/GraphQL) to view models (UI).
All presentation logic and transformations live here.
"""
from ..network.rest import RESTPullRequest
from ..view import UIPullRequest
from ..formatting import (
    format_date,
    get_pr_status_icon,
    format_pr_stats,
    format_branch_info,
    calculate_review_summary,
)


def from_rest_pr(rest_pr: RESTPullRequest) -> UIPullRequest:
    """
    Convert REST PR to UI PR.

    Applies all transformations and pre-calculates display fields.

    Args:
        rest_pr: RESTPullRequest from REST API

    Returns:
        UIPullRequest ready for rendering
    """
    # Extract label names from label objects
    label_names = [label.get("name", "") for label in rest_pr.labels]

    return UIPullRequest(
        number=rest_pr.number,
        title=rest_pr.title,
        body=rest_pr.body,
        status_icon=get_pr_status_icon(rest_pr.state, rest_pr.isDraft),
        state=rest_pr.state,
        author_name=rest_pr.author.login,
        head_ref=rest_pr.headRefName,
        base_ref=rest_pr.baseRefName,
        branch_info=format_branch_info(rest_pr.headRefName, rest_pr.baseRefName),
        stats=format_pr_stats(rest_pr.additions, rest_pr.deletions),
        files_changed=rest_pr.changedFiles,
        is_mergeable=(rest_pr.mergeable == "MERGEABLE"),
        is_draft=rest_pr.isDraft,
        review_summary=calculate_review_summary(rest_pr.reviews),
        labels=label_names,
        formatted_created_at=format_date(rest_pr.createdAt) if rest_pr.createdAt else "",
        formatted_updated_at=format_date(rest_pr.updatedAt) if rest_pr.updatedAt else "",
    )
