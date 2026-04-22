"""
User Mapper

Maps NetworkJiraUser (network layer) to UIJiraUser (view layer).
"""

from ..network.rest.user import NetworkJiraUser
from ..view import UIJiraUser


def from_network_user(network_user: NetworkJiraUser) -> UIJiraUser:
    """
    Map NetworkJiraUser to UIJiraUser.

    Args:
        network_user: Network model from API

    Returns:
        UIJiraUser optimized for rendering
    """
    return UIJiraUser(
        account_id=network_user.accountId or "",
        display_name=network_user.displayName,
        email=network_user.emailAddress or "Unknown",
        active=network_user.active
    )


__all__ = ["from_network_user"]
