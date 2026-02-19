# plugins/titan-plugin-git/titan_plugin_git/clients/services/branch_service.py
"""
Branch Service

Business logic for Git branch operations.
Uses network layer to execute commands, parses to network models, maps to view models.
"""
from typing import List

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError
from titan_cli.core.logging import log_client_operation

from ..network import GitNetwork
from ...models.network.branch import NetworkGitBranch
from ...models.view.branch import UIGitBranch
from ...models.mappers import from_network_branch
from ...exceptions import GitCommandError
from ...messages import msg


class BranchService:
    """
    Service for Git branch operations.

    Handles fetching, creating, deleting, and checking out branches.
    Returns view models ready for UI rendering.
    """

    def __init__(self, git_network: GitNetwork):
        """
        Initialize Branch service.

        Args:
            git_network: GitNetwork instance for command execution
        """
        self.git = git_network

    @log_client_operation()
    def get_current_branch(self) -> ClientResult[str]:
        """
        Get current branch name.

        Returns:
            ClientResult[str] with current branch name
        """
        try:
            branch = self.git.run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            return ClientSuccess(data=branch, message=f"Current branch: {branch}")
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="BRANCH_ERROR")

    @log_client_operation()
    def get_branches(self, remote: bool = False) -> ClientResult[List[UIGitBranch]]:
        """
        List branches.

        Args:
            remote: List remote branches instead of local

        Returns:
            ClientResult[List[UIGitBranch]]
        """
        try:
            args = ["git", "branch"]
            if remote:
                args.append("-r")
            else:
                args.append("-l")

            output = self.git.run_command(args)

            network_branches = []
            for line in output.splitlines():
                is_current = line.startswith("*")
                name = line[2:].strip() if is_current else line.strip()

                # Skip 'origin/HEAD -> origin/main' type refs
                if name.startswith("origin/HEAD"):
                    continue

                is_remote_branch = remote
                upstream = None

                # Try to get upstream if local and current branch
                if not remote and is_current:
                    try:
                        upstream_output = self.git.run_command(
                            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                            check=False
                        )
                        upstream = upstream_output.strip()
                    except GitCommandError:
                        pass  # No upstream configured

                network_branches.append(NetworkGitBranch(
                    name=name,
                    is_current=is_current,
                    is_remote=is_remote_branch,
                    upstream=upstream
                ))

            # Map to UI models
            ui_branches = [from_network_branch(b) for b in network_branches]

            return ClientSuccess(
                data=ui_branches,
                message=f"Found {len(ui_branches)} branches"
            )

        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="BRANCH_LIST_ERROR")

    @log_client_operation()
    def create_branch(
        self, branch_name: str, start_point: str = "HEAD"
    ) -> ClientResult[None]:
        """
        Create a new branch.

        Args:
            branch_name: Name for new branch
            start_point: Starting point (commit/branch)

        Returns:
            ClientResult[None]
        """
        try:
            self.git.run_command(["git", "branch", branch_name, start_point])
            return ClientSuccess(
                data=None,
                message=f"Branch '{branch_name}' created"
            )
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="BRANCH_CREATE_ERROR")

    @log_client_operation()
    def delete_branch(
        self, branch: str, force: bool = False
    ) -> ClientResult[None]:
        """
        Delete a branch.

        Args:
            branch: Branch name to delete
            force: Force deletion (git branch -D)

        Returns:
            ClientResult[None]
        """
        try:
            delete_arg = "-D" if force else "-d"
            self.git.run_command(["git", "branch", delete_arg, branch])
            return ClientSuccess(
                data=None,
                message=f"Branch '{branch}' deleted"
            )
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="BRANCH_DELETE_ERROR")

    @log_client_operation()
    def checkout(self, branch: str) -> ClientResult[None]:
        """
        Checkout a branch.

        Args:
            branch: Branch name to checkout

        Returns:
            ClientResult[None]
        """
        try:
            # Check if branch exists locally or remotely
            try:
                self.git.run_command(
                    ["git", "show-ref", "--verify", f"refs/heads/{branch}"],
                    check=False
                )
                self.git.run_command(
                    ["git", "show-ref", "--verify", f"refs/remotes/origin/{branch}"],
                    check=False
                )
            except GitCommandError:
                return ClientError(
                    error_message=msg.Git.BRANCH_NOT_FOUND.format(branch=branch),
                    error_code="BRANCH_NOT_FOUND",
                    log_level="warning"
                )

            # Checkout
            self.git.run_command(["git", "checkout", branch])
            return ClientSuccess(
                data=None,
                message=f"Checked out branch '{branch}'"
            )

        except GitCommandError as e:
            # Check if it's a dirty working tree error
            error_str = str(e)
            if "would be overwritten" in error_str or "uncommitted changes" in error_str:
                return ClientError(
                    error_message=msg.Git.CANNOT_CHECKOUT_UNCOMMITTED_CHANGES,
                    error_code="DIRTY_WORKING_TREE",
                    log_level="warning"
                )
            return ClientError(error_message=str(e), error_code="CHECKOUT_ERROR")

    @log_client_operation()
    def branch_exists_on_remote(
        self, branch: str, remote: str = "origin"
    ) -> ClientResult[bool]:
        """
        Check if a branch exists on remote.

        Args:
            branch: Branch name to check
            remote: Remote name (default: "origin")

        Returns:
            ClientResult[bool] with True if exists, False otherwise
        """
        try:
            result = self.git.run_command(
                ["git", "ls-remote", "--heads", remote, branch],
                check=False
            )
            exists = bool(result.strip())
            return ClientSuccess(
                data=exists,
                message=f"Branch '{branch}' {'exists' if exists else 'does not exist'} on {remote}"
            )
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="REMOTE_CHECK_ERROR")
