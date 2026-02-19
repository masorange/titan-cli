"""
Worktree Operations

Pure business logic for git worktree operations.
These functions wrap git worktree commands without UI dependencies.
"""

import os
from typing import Tuple
from titan_cli.core.result import ClientSuccess, ClientError


def setup_worktree(
    git_client,
    pr_number: int,
    branch: str,
    base_path: str = ".titan/worktrees",
    remote: str = "origin"
) -> Tuple[str, bool]:
    """
    Create a git worktree for PR review.

    Args:
        git_client: Git client instance
        pr_number: PR number (used in worktree name)
        branch: Branch to checkout in worktree
        base_path: Base directory for worktrees
        remote: Remote name (default: "origin")

    Returns:
        Tuple of (absolute_path, created_successfully)

    Example:
        >>> abs_path, created = setup_worktree(git, 123, "feature-branch")
        >>> abs_path
        '/home/user/project/.titan/worktrees/titan-review-123'
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
            result = git_client.remove_worktree(worktree_path, force=True)
            match result:
                case ClientSuccess():
                    pass
                case ClientError():
                    pass  # Worktree might not exist
        except Exception:
            pass

        # Create new worktree from remote branch in detached mode
        # This avoids "branch already checked out" errors and works even if branch doesn't exist locally
        remote_ref = f"{remote}/{branch}"

        result = git_client.create_worktree(
            path=worktree_path,
            branch=remote_ref,
            create_branch=False,
            detached=True
        )

        match result:
            case ClientSuccess():
                return (full_worktree_path, True)
            case ClientError():
                return ("", False)

    except Exception:
        return ("", False)


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
    """
    result = git_client.remove_worktree(worktree_path, force=True)
    match result:
        case ClientSuccess():
            return True
        case ClientError():
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
    """
    result = git_client.commit_in_worktree(worktree_path, message, add_all, no_verify)
    match result:
        case ClientSuccess(data=commit_hash):
            return commit_hash
        case ClientError(error_message=err):
            raise Exception(f"Failed to commit in worktree: {err}")
