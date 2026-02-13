"""
Jira Network Layer

HTTP/REST API communication.
Returns raw JSON responses (dicts).
"""

from .jira_network import JiraNetwork

__all__ = ["JiraNetwork"]
