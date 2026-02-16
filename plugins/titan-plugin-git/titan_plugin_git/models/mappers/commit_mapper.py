"""Mapper for Git commit: Network model → UI model."""
import re
from ..network.commit import NetworkGitCommit
from ..view.commit import UIGitCommit


def from_network_commit(network_commit: NetworkGitCommit) -> UIGitCommit:
    """
    Transform network commit model to UI commit model.

    Args:
        network_commit: Raw commit data from git CLI

    Returns:
        Formatted UI commit model with short hash and formatted date

    Example:
        >>> network = NetworkGitCommit(hash="abc123...", message="feat: Add feature", author="John <john@example.com>", date="2026-01-15")
        >>> ui = from_network_commit(network)
        >>> ui.short_hash
        'abc1234'
        >>> ui.author_short
        'John'
    """
    # Short hash (first 7 characters)
    short_hash = network_commit.hash[:7] if len(network_commit.hash) >= 7 else network_commit.hash

    # Message subject (first line)
    message_subject = network_commit.message.split('\n')[0] if network_commit.message else ""

    # Author short (name without email)
    author_short = network_commit.author
    # Remove email if present: "John Doe <john@example.com>" → "John Doe"
    email_match = re.search(r'^(.+?)\s*<.+>$', network_commit.author)
    if email_match:
        author_short = email_match.group(1).strip()

    # Formatted date (for now, just use the raw date)
    # TODO: Could add relative time formatting ("2 days ago")
    formatted_date = network_commit.date

    return UIGitCommit(
        hash=network_commit.hash,
        short_hash=short_hash,
        message=network_commit.message,
        message_subject=message_subject,
        author=network_commit.author,
        author_short=author_short,
        date=network_commit.date,
        formatted_date=formatted_date,
    )
