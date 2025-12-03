"""
Git Models

Data models for Git operations.
"""

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class GitBranch:
    """Git branch representation"""
    name: str
    is_current: bool = False
    is_remote: bool = False
    upstream: Optional[str] = None


@dataclass
class GitStatus:
    """Git repository status"""
    branch: str
    is_clean: bool
    modified_files: List[str]
    untracked_files: List[str]
    staged_files: List[str]
    ahead: int = 0
    behind: int = 0


@dataclass
class GitCommit:
    """Git commit representation"""
    hash: str
    short_hash: str
    message: str
    author: str
    date: str
