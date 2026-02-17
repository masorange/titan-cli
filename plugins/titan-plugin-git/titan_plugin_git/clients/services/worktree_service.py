# plugins/titan-plugin-git/titan_plugin_git/clients/services/worktree_service.py
"""
Worktree Service

Business logic for Git worktree operations.
Uses network layer to execute commands, parses to network models, maps to view models.
"""
from typing import List

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..network import GitNetwork
from ...models.network.worktree import NetworkGitWorktree
from ...models.view.worktree import UIGitWorktree
from ...models.mappers import from_network_worktree
from ...exceptions import GitCommandError


class WorktreeService:
    """
    Service for Git worktree operations.

    Handles creating, removing, listing, and running commands in worktrees.
    Returns view models ready for UI rendering.
    """

    def __init__(self, git_network: GitNetwork):
        """
        Initialize Worktree service.

        Args:
            git_network: GitNetwork instance for command execution
        """
        self.git = git_network

    def create_worktree(
        self, path: str, branch: str, create_branch: bool = False, detached: bool = False
    ) -> ClientResult[None]:
        """
        Create a new worktree at the specified path.

        Args:
            path: Path where to create the worktree
            branch: Branch or ref to checkout in the worktree
            create_branch: If True, create the branch
            detached: If True, create in detached HEAD mode (allows using same branch as current repo)

        Returns:
            ClientResult[None]
        """
        try:
            args = ["git", "worktree", "add"]

            if detached:
                args.append("--detach")

            if create_branch:
                args.extend(["-b", branch])

            args.append(path)

            if not create_branch:
                args.append(branch)

            self.git.run_command(args)
            return ClientSuccess(data=None, message=f"Worktree created at {path}")

        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="WORKTREE_CREATE_ERROR")

    def remove_worktree(self, path: str, force: bool = False) -> ClientResult[None]:
        """
        Remove a worktree.

        Args:
            path: Path to the worktree to remove
            force: Force removal even if worktree is dirty

        Returns:
            ClientResult[None]
        """
        try:
            args = ["git", "worktree", "remove", path]

            if force:
                args.append("--force")

            self.git.run_command(args)
            return ClientSuccess(data=None, message=f"Worktree removed: {path}")

        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="WORKTREE_REMOVE_ERROR")

    def list_worktrees(self) -> ClientResult[List[UIGitWorktree]]:
        """
        List all worktrees.

        Returns:
            ClientResult[List[UIGitWorktree]]
        """
        try:
            output = self.git.run_command(["git", "worktree", "list", "--porcelain"])

            network_worktrees = []
            current_worktree = {}

            for line in output.splitlines():
                line = line.strip()
                if not line:
                    if current_worktree:
                        # Create NetworkGitWorktree from parsed data
                        network_worktrees.append(NetworkGitWorktree(
                            path=current_worktree.get("path", ""),
                            branch=current_worktree.get("branch"),
                            commit=current_worktree.get("commit"),
                            is_bare=current_worktree.get("bare", False),
                            is_detached=current_worktree.get("detached", False)
                        ))
                        current_worktree = {}
                    continue

                if line.startswith("worktree "):
                    current_worktree["path"] = line.split("worktree ", 1)[1]
                elif line.startswith("HEAD "):
                    current_worktree["commit"] = line.split("HEAD ", 1)[1]
                elif line.startswith("branch "):
                    current_worktree["branch"] = line.split("branch ", 1)[1].replace("refs/heads/", "")
                elif line == "bare":
                    current_worktree["bare"] = True
                elif line == "detached":
                    current_worktree["detached"] = True

            # Handle last worktree if exists
            if current_worktree:
                network_worktrees.append(NetworkGitWorktree(
                    path=current_worktree.get("path", ""),
                    branch=current_worktree.get("branch"),
                    commit=current_worktree.get("commit"),
                    is_bare=current_worktree.get("bare", False),
                    is_detached=current_worktree.get("detached", False)
                ))

            # Map to UI models
            ui_worktrees = [from_network_worktree(wt) for wt in network_worktrees]

            return ClientSuccess(
                data=ui_worktrees,
                message=f"Found {len(ui_worktrees)} worktrees"
            )

        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="WORKTREE_LIST_ERROR")

    def run_in_worktree(self, worktree_path: str, args: List[str]) -> ClientResult[str]:
        """
        Run a git command in a specific worktree.

        Args:
            worktree_path: Path to the worktree
            args: Command arguments (including 'git')

        Returns:
            ClientResult[str] with command stdout
        """
        try:
            # Use git -C <path> to run command in worktree
            if args[0] == "git":
                args = ["git", "-C", worktree_path] + args[1:]

            output = self.git.run_command(args, cwd=worktree_path)
            return ClientSuccess(data=output, message="Command executed in worktree")

        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="WORKTREE_COMMAND_ERROR")
