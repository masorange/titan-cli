"""UI/View models for Git plugin - pre-formatted for display."""
from .branch import UIGitBranch
from .status import UIGitStatus
from .commit import UIGitCommit, UIGitGraphRow
from .tag import UIGitTag
from .worktree import UIGitWorktree
from .stash import UIGitStash
from .merge import MergeStatus, UIMergeResult
from .diff import (
    UIDiffHunk,
    UIDiffLine,
    UIFileChange,
    UIFileChurn,
    UIFileDiff,
    UIUncommittedFiles,
)

__all__ = [
    "UIGitBranch",
    "UIGitStatus",
    "UIGitCommit",
    "UIGitGraphRow",
    "UIGitTag",
    "UIGitWorktree",
    "UIGitStash",
    "MergeStatus",
    "UIMergeResult",
    "UIFileChurn",
    "UIFileChange",
    "UIUncommittedFiles",
    "UIFileDiff",
    "UIDiffHunk",
    "UIDiffLine",
]
