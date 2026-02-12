"""
Worktree Operations

Pure business logic for git worktree operations.
These functions wrap git worktree commands without UI dependencies.
"""

import os
from typing import Tuple, Optional


def setup_worktree(
    git_client,
    pr_number: int,
    branch: str,
    base_path: str = ".titan/worktrees"
) -> Tuple[str, str, bool]:
    """
    Create a git worktree for PR review.

    Args:
        git_client: Git client instance
        pr_number: PR number (used in worktree name)
        branch: Branch to checkout in worktree
        base_path: Base directory for worktrees

    Returns:
        Tuple of (relative_path, absolute_path, created_successfully)

    Example:
        >>> rel_path, abs_path, created = setup_worktree(git, 123, "feature-branch")
        >>> rel_path
        '.titan/worktrees/titan-review-123'
        >>> created
        True
    """
    try:
        worktree_name = f"titan-review-{pr_number}"
        worktree_path = f"{base_path}/{worktree_name}"
        original_cwd = os.getcwd()
        full_worktree_path = os.path.join(original_cwd, worktree_path)

        # Remove worktree if it already exists
        try:
            git_client.remove_worktree(worktree_path, force=True)
        except Exception:
            pass  # Worktree might not exist

        # Create new worktree from branch
        git_client.create_worktree(
            path=worktree_path,
            branch=branch,
            create_branch=False
        )

        return (worktree_path, full_worktree_path, True)

    except Exception:
        return ("", "", False)


def cleanup_worktree(
    git_client,
    worktree_path: str
) -> bool:
    """
    Remove a git worktree.

    Args:
        git_client: Git client instance
        worktree_path: Path to worktree (relative or absolute)

    Returns:
        True if successful, False otherwise

    Example:
        >>> cleanup_worktree(git, ".titan/worktrees/titan-review-123")
        True
    """
    try:
        git_client.remove_worktree(worktree_path, force=True)
        return True
    except Exception:
        return False


def commit_in_worktree(
    git_client,
    worktree_path: str,
    message: str,
    add_all: bool = True,
    no_verify: bool = False
) -> str:
    """
    Create a commit in a worktree.

    This is the pure business logic extracted from worktree_commit step.
    Can be called from any step without showing UI.

    Args:
        git_client: Git client instance
        worktree_path: Path to worktree
        message: Commit message
        add_all: Stage all changes before committing
        no_verify: Skip pre-commit hooks

    Returns:
        Commit hash (40-char SHA)

    Raises:
        Exception: If commit fails

    Example:
        >>> commit_hash = commit_in_worktree(
        ...     git, "/tmp/worktree",
        ...     "Fix bug", add_all=True, no_verify=True
        ... )
        >>> len(commit_hash)
        40
    """
    # Stage files if requested
    if add_all:
        git_client.run_in_worktree(worktree_path, ["git", "add", "--all"])

    # Build commit command
    commit_args = ["git", "commit"]

    if no_verify:
        commit_args.append("--no-verify")

    commit_args.extend(["-m", message])

    # Create commit
    git_client.run_in_worktree(worktree_path, commit_args)

    # Get commit hash
    commit_hash = git_client.run_in_worktree(
        worktree_path,
        ["git", "rev-parse", "HEAD"]
    ).strip()

    return commit_hash


def push_from_worktree(
    git_client,
    worktree_path: str,
    remote: str = "origin",
    branch: Optional[str] = None,
    set_upstream: bool = False
) -> bool:
    """
    Push from a worktree to remote.

    This is the pure business logic extracted from worktree_push step.

    Args:
        git_client: Git client instance
        worktree_path: Path to worktree
        remote: Remote name (default: "origin")
        branch: Branch to push (auto-detects if None)
        set_upstream: Set upstream tracking

    Returns:
        True if successful, False otherwise

    Example:
        >>> push_from_worktree(git, "/tmp/worktree", branch="feature-x")
        True
    """
    try:
        # Auto-detect branch if not provided
        if not branch:
            result = git_client.run_in_worktree(
                worktree_path,
                ["git", "branch", "--show-current"]
            )
            branch = result.strip()

        if not branch:
            return False

        # Build push command
        push_args = ["git", "push"]

        if set_upstream:
            push_args.append("-u")

        push_args.extend([remote, branch])

        # Push
        git_client.run_in_worktree(worktree_path, push_args)

        return True

    except Exception:
        return False
