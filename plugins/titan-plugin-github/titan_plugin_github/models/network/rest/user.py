# plugins/titan-plugin-github/titan_plugin_github/models/network/rest/user.py
"""
REST API User Model

Faithful representation of GitHub user data from REST API (gh CLI JSON responses).
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class NetworkUser:
    """
    GitHub user from REST API.

    Faithful to gh CLI JSON output (e.g., from `gh pr view --json author`).
    Field names match REST API response exactly.

    Examples:
        >>> data = {"login": "john", "name": "John Doe", "email": "john@example.com"}
        >>> user = NetworkUser.from_json(data)
    """
    login: str
    name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'NetworkUser':
        """
        Create NetworkUser from gh CLI JSON response.

        Args:
            data: User data from GitHub REST API

        Returns:
            NetworkUser instance

        Examples:
            >>> data = {"login": "john", "name": "John Doe"}
            >>> user = NetworkUser.from_json(data)
        """
        if not data:
            return cls(login="unknown")

        return cls(
            login=data.get("login", "unknown"),
            name=data.get("name"),
            email=data.get("email"),
            avatar_url=data.get("avatar_url")
        )
