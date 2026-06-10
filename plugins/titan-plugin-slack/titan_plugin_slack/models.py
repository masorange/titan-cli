"""Core models for the Slack plugin baseline."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class NetworkSlackChannel:
    """Raw Slack channel data normalized from the Web API."""

    id: str
    name: str
    is_channel: bool = True
    is_private: bool = False


@dataclass
class NetworkSlackUser:
    """Raw Slack user data normalized from the Web API."""

    id: str
    name: str
    real_name: Optional[str] = None
    is_bot: bool = False
    is_active: bool = True


@dataclass
class SlackMessageRef:
    """Stable reference to a posted Slack message."""

    channel: str
    ts: str
    thread_ts: Optional[str] = None
    permalink: Optional[str] = None


@dataclass
class NetworkSlackMessage:
    """Raw Slack message data normalized from the Web API."""

    ts: str
    text: str
    user: Optional[str] = None
    thread_ts: Optional[str] = None
    reply_count: int = 0
    subtype: Optional[str] = None
