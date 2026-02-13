# plugins/titan-plugin-github/titan_plugin_github/models/network/graphql/user.py
"""
GraphQL User Model

Faithful representation of GitHub Actor/User from GraphQL API.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class GraphQLUser:
    """
    GitHub user/actor from GraphQL API.

    Faithful to GraphQL Actor interface.
    See: https://docs.github.com/en/graphql/reference/interfaces#actor

    Field names match GraphQL schema exactly.

    Examples:
        >>> data = {"login": "john", "name": "John Doe"}
        >>> user = GraphQLUser.from_graphql(data)
    """
    login: str
    name: Optional[str] = None
    email: Optional[str] = None

    @classmethod
    def from_graphql(cls, data: Dict[str, Any]) -> 'GraphQLUser':
        """
        Create GraphQLUser from GraphQL response.

        Args:
            data: Actor/User node from GraphQL query

        Returns:
            GraphQLUser instance
        """
        if not data:
            return cls(login="unknown")

        return cls(
            login=data.get("login", "unknown"),
            name=data.get("name"),
            email=data.get("email")
        )
