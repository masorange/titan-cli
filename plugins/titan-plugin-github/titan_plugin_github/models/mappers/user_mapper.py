"""Mapper from GraphQL users to UI availability."""

from ..network.graphql import GraphQLUser
from ..view import UIUserAvailability


def from_graphql_user_availability(user: GraphQLUser) -> UIUserAvailability:
    """A user's Busy status as the UI shows it; no status means available."""
    status = user.status
    return UIUserAvailability(
        login=user.login,
        is_busy=bool(status and status.indicatesLimitedAvailability),
        status_message=(status.message or "") if status else "",
    )
