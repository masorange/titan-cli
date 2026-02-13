"""
GitHub Network Layer

Low-level network operations for GitHub API.
Handles command execution, authentication, and error handling.
Returns raw data (strings/dicts) without model conversion.
"""

from .gh_network import GHNetwork
from .graphql_network import GraphQLNetwork
from . import graphql_queries

__all__ = [
    "GHNetwork",
    "GraphQLNetwork",
    "graphql_queries",
]
