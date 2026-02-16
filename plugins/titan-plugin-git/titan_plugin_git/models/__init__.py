"""
Git Models

Exports both network and UI models for backward compatibility.
"""

# Network models
from .network import (
    NetworkGitBranch,
    NetworkGitStatus,
    NetworkGitCommit,
    NetworkGitTag,
    NetworkGitWorktree,
)

# UI/View models
from .view import (
    UIGitBranch,
    UIGitStatus,
    UIGitCommit,
    UIGitTag,
    UIGitWorktree,
)

# Mappers
from .mappers import (
    from_network_branch,
    from_network_status,
    from_network_commit,
    from_network_tag,
    from_network_worktree,
)

# For backward compatibility, export old names pointing to UI models
GitBranch = UIGitBranch
GitStatus = UIGitStatus
GitCommit = UIGitCommit

__all__ = [
    # Network models
    "NetworkGitBranch",
    "NetworkGitStatus",
    "NetworkGitCommit",
    "NetworkGitTag",
    "NetworkGitWorktree",
    # UI models
    "UIGitBranch",
    "UIGitStatus",
    "UIGitCommit",
    "UIGitTag",
    "UIGitWorktree",
    # Mappers
    "from_network_branch",
    "from_network_status",
    "from_network_commit",
    "from_network_tag",
    "from_network_worktree",
    # Backward compatibility
    "GitBranch",
    "GitStatus",
    "GitCommit",
]
