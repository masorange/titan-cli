"""What the pane shows: the snapshot `read_repo` builds from the git plugin's UI model and the drawing reads."""
from dataclasses import dataclass, field
from typing import List, Optional

from titan_plugin_git.models.view import UIGitCommit


@dataclass(frozen=True)
class Repo:
    branch: str
    has_upstream: bool = False
    ahead: int = 0
    behind: int = 0
    added: int = 0
    removed: int = 0
    commits: List[UIGitCommit] = field(default_factory=list)
    error: Optional[str] = None
