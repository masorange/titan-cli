# plugins/titan-plugin-git/titan_plugin_git/clients/services/remote_service.py
"""
Remote Service

Business logic for Git remote operations.
Uses network layer to execute commands for push, pull, fetch operations.
"""
import re
from typing import Optional, Tuple

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..network import GitNetwork
from ...exceptions import GitCommandError


class RemoteService:
    """
    Service for Git remote operations.

    Handles push, pull, fetch, and remote repository information.
    """

    def __init__(self, git_network: GitNetwork):
        """
        Initialize Remote service.

        Args:
            git_network: GitNetwork instance for command execution
        """
        self.git = git_network

    def push(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
        set_upstream: bool = False,
        tags: bool = False
    ) -> ClientResult[None]:
        """
        Push to remote.

        Args:
            remote: Remote name
            branch: Branch to push (default: current)
            set_upstream: Set upstream tracking
            tags: Push tags to remote

        Returns:
            ClientResult[None]
        """
        try:
            args = ["git", "push"]

            if set_upstream:
                args.append("-u")

            if tags:
                args.append("--tags")

            args.append(remote)

            if branch:
                args.append(branch)

            self.git.run_command(args)
            return ClientSuccess(data=None, message=f"Pushed to {remote}")

        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="PUSH_ERROR")

    def pull(
        self, remote: str = "origin", branch: Optional[str] = None
    ) -> ClientResult[None]:
        """
        Pull from remote.

        Args:
            remote: Remote name
            branch: Branch to pull (default: current)

        Returns:
            ClientResult[None]
        """
        try:
            args = ["git", "pull", remote]

            if branch:
                args.append(branch)

            self.git.run_command(args)
            return ClientSuccess(data=None, message=f"Pulled from {remote}")

        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="PULL_ERROR")

    def fetch(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
        all: bool = False
    ) -> ClientResult[None]:
        """
        Fetch from remote.

        Args:
            remote: Remote name
            branch: Specific branch to fetch (optional)
            all: Fetch from all remotes

        Returns:
            ClientResult[None]
        """
        try:
            args = ["git", "fetch"]

            if all:
                args.append("--all")
            else:
                args.append(remote)
                if branch:
                    args.append(branch)

            self.git.run_command(args)
            return ClientSuccess(data=None, message="Fetch completed")

        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="FETCH_ERROR")

    def get_github_repo_info(self) -> ClientResult[Tuple[Optional[str], Optional[str]]]:
        """
        Extract GitHub repository owner and name from 'origin' remote URL.

        Returns:
            ClientResult[Tuple[Optional[str], Optional[str]]] with (repo_owner, repo_name)
        """
        try:
            url = self.git.run_command(["git", "remote", "get-url", "origin"])

            # Parse: git@github.com:owner/repo.git or https://github.com/owner/repo.git
            match = re.search(r'github\.com[:/]([^/]+)/([^/.]+)', url)
            if match:
                repo_owner = match.group(1)
                repo_name = match.group(2)
                return ClientSuccess(
                    data=(repo_owner, repo_name),
                    message=f"Detected GitHub repo: {repo_owner}/{repo_name}"
                )
            else:
                return ClientSuccess(
                    data=(None, None),
                    message="Not a GitHub repository"
                )

        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="REMOTE_ERROR")
