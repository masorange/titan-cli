"""
Git Exceptions

Custom exceptions for Git operations.
"""


class GitError(Exception):
    """Base exception for Git errors"""
    pass


class GitCommandError(GitError):
    """Git command failed"""
    pass


class GitClientError(GitError):
    """Git client initialization or configuration error"""
    pass


class GitBranchNotFoundError(GitError):
    """Branch not found"""
    pass


class GitDirtyWorkingTreeError(GitError):
    """Working tree has uncommitted changes"""
    pass


class GitNotRepositoryError(GitError):
    """Not a git repository"""
    pass


class GitMergeConflictError(GitError):
    """Merge conflict occurred"""
    pass