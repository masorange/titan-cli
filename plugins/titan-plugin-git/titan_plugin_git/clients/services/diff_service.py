# plugins/titan-plugin-git/titan_plugin_git/clients/services/diff_service.py
"""
Diff Service

Business logic for Git diff operations.
Uses network layer to execute commands and returns diff outputs.
"""
from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..network import GitNetwork
from ...exceptions import GitCommandError


class DiffService:
    """
    Service for Git diff operations.

    Handles getting diffs between references, branches, files, and states.
    Returns raw diff output as strings.
    """

    def __init__(self, git_network: GitNetwork, default_remote: str = "origin"):
        """
        Initialize Diff service.

        Args:
            git_network: GitNetwork instance for command execution
            default_remote: Default remote name (from config)
        """
        self.git = git_network
        self.default_remote = default_remote

    def get_diff(self, base_ref: str, head_ref: str = "HEAD") -> ClientResult[str]:
        """
        Get diff between two references.

        Args:
            base_ref: Base reference (branch, commit, tag)
            head_ref: Head reference (default: "HEAD")

        Returns:
            ClientResult[str] with diff output
        """
        try:
            diff = self.git.run_command(
                ["git", "diff", f"{base_ref}...{head_ref}"],
                check=False
            )
            return ClientSuccess(data=diff, message="Diff retrieved")
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="DIFF_ERROR")

    def get_uncommitted_diff(self) -> ClientResult[str]:
        """
        Get diff of all uncommitted changes (staged + unstaged + untracked).

        Uses git add --intent-to-add to make untracked files visible.

        Returns:
            ClientResult[str] with diff output
        """
        try:
            # Add untracked files to index without staging content
            self.git.run_command(["git", "add", "--intent-to-add", "."], check=False)

            # git diff HEAD shows all changes vs last commit
            diff = self.git.run_command(["git", "diff", "HEAD"], check=False)
            return ClientSuccess(data=diff, message="Uncommitted diff retrieved")
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="DIFF_ERROR")

    def get_staged_diff(self) -> ClientResult[str]:
        """
        Get diff of staged changes only (index vs HEAD).

        Returns:
            ClientResult[str] with diff output
        """
        try:
            diff = self.git.run_command(["git", "diff", "--cached"], check=False)
            return ClientSuccess(data=diff, message="Staged diff retrieved")
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="DIFF_ERROR")

    def get_unstaged_diff(self) -> ClientResult[str]:
        """
        Get diff of unstaged changes only (working directory vs index).

        Returns:
            ClientResult[str] with diff output
        """
        try:
            diff = self.git.run_command(["git", "diff"], check=False)
            return ClientSuccess(data=diff, message="Unstaged diff retrieved")
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="DIFF_ERROR")

    def get_uncommitted_diff_stat(self) -> ClientResult[str]:
        """
        Get diff stat summary of uncommitted changes (working tree vs HEAD).

        Shows summary of files changed, insertions, and deletions.

        Returns:
            ClientResult[str] with diff stat output
        """
        try:
            # Add untracked files to index without staging content
            self.git.run_command(["git", "add", "--intent-to-add", "."], check=False)

            # git diff --stat=300 HEAD shows all changes vs last commit (300 prevents path truncation with ...)
            diff_stat = self.git.run_command(["git", "diff", "--stat=300", "HEAD"], check=False)
            return ClientSuccess(data=diff_stat, message="Uncommitted diff stat retrieved")
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="DIFF_ERROR")

    def get_file_diff(self, file_path: str) -> ClientResult[str]:
        """
        Get diff for a specific file.

        Args:
            file_path: Path to the file

        Returns:
            ClientResult[str] with diff output
        """
        try:
            diff = self.git.run_command(
                ["git", "diff", "HEAD", "--", file_path],
                check=False
            )
            return ClientSuccess(data=diff, message=f"Diff for {file_path} retrieved")
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="DIFF_ERROR")

    def get_branch_diff(self, base_branch: str, head_branch: str) -> ClientResult[str]:
        """
        Get diff between two branches.

        Args:
            base_branch: Base branch name
            head_branch: Head branch name

        Returns:
            ClientResult[str] with diff output
        """
        try:
            diff = self.git.run_command(
                ["git", "diff", f"{self.default_remote}/{base_branch}...{head_branch}"],
                check=False
            )
            return ClientSuccess(
                data=diff,
                message=f"Diff between {base_branch} and {head_branch} retrieved"
            )
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="DIFF_ERROR")

    def get_diff_stat(self, base_ref: str, head_ref: str = "HEAD") -> ClientResult[str]:
        """
        Get diff stat summary between two references.

        Args:
            base_ref: Base reference
            head_ref: Head reference (default: "HEAD")

        Returns:
            ClientResult[str] with diff stat output
        """
        try:
            diff_stat = self.git.run_command(
                ["git", "diff", "--stat=300", f"{base_ref}...{head_ref}"],
                check=False
            )
            return ClientSuccess(data=diff_stat, message="Diff stat retrieved")
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="DIFF_ERROR")
