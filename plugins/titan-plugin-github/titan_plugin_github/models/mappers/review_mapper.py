# plugins/titan-plugin-github/titan_plugin_github/models/mappers/review_mapper.py
"""
Review Mapper

Converts network models (REST) to view models (UI).
"""
from ..network.rest import NetworkReview
from ..view import UIReview
from ..formatting import format_date, get_review_state_icon, format_short_sha


def from_network_review(network_review: NetworkReview) -> UIReview:
    """
    Convert Network Review to UI Review.

    Args:
        network_review: NetworkReview from REST API

    Returns:
        UIReview with all fields pre-formatted for display
    """
    # Extract author name (prefer name, fallback to login)
    author_name = network_review.user.name or network_review.user.login

    # Format submitted date
    formatted_submitted_at = format_date(network_review.submitted_at) if network_review.submitted_at else ""

    # Get state icon
    state_icon = get_review_state_icon(network_review.state)

    # Format commit SHA
    commit_id_short = format_short_sha(network_review.commit_id)

    return UIReview(
        id=network_review.id,
        author_name=author_name,
        body=network_review.body,
        state_icon=state_icon,
        state=network_review.state,
        formatted_submitted_at=formatted_submitted_at,
        commit_id_short=commit_id_short,
    )


__all__ = ["from_network_review"]
