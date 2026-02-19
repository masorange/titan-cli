# plugins/titan-plugin-git/titan_plugin_git/clients/services/status_service.py
"""
Status Service

Business logic for Git status operations.
Uses network layer to execute commands, parses to network models, maps to view models.
"""
from typing import Tuple

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError
from titan_cli.core.logging import log_client_operation

from ..network import GitNetwork
from ...models.network.status import NetworkGitStatus
from ...models.view.status import UIGitStatus
from ...models.mappers import from_network_status
from ...exceptions import GitCommandError


class StatusService:
    """
    Service for Git status operations.

    Handles repository status and uncommitted changes checking.
    Returns view models ready for UI rendering.
    """

    def __init__(self, git_network: GitNetwork):
        """
        Initialize Status service.

        Args:
            git_network: GitNetwork instance for command execution
        """
        self.git = git_network

    @log_client_operation()
    def get_status(self) -> ClientResult[UIGitStatus]:
        """
        Get repository status.

        Returns:
            ClientResult[UIGitStatus]
        """
        try:
            # Get current branch
            branch = self.git.run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])

            # Get status
            status_output = self.git.run_command(["git", "status", "--short"])

            modified = []
            untracked = []
            staged = []

            for line in status_output.splitlines():
                if not line.strip():
                    continue

                status_code = line[:2]
                file_path = line[3:].strip()

                if status_code[0] != ' ' and status_code[0] != '?':
                    staged.append(file_path)

                if status_code[1] == 'M':
                    modified.append(file_path)
                elif status_code == '??':
                    untracked.append(file_path)

            is_clean = not (modified or untracked or staged)

            # Get ahead/behind status
            ahead, behind = self._get_upstream_status()

            # Create network model
            network_status = NetworkGitStatus(
                branch=branch,
                is_clean=is_clean,
                modified_files=modified,
                untracked_files=untracked,
                staged_files=staged,
                ahead=ahead,
                behind=behind
            )

            # Map to UI model
            ui_status = from_network_status(network_status)

            return ClientSuccess(
                data=ui_status,
                message="Status retrieved"
            )

        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="STATUS_ERROR")

    @log_client_operation()
    def has_uncommitted_changes(self) -> ClientResult[bool]:
        """
        Check if repository has uncommitted changes.

        Returns:
            ClientResult[bool] with True if there are uncommitted changes
        """
        try:
            status_output = self.git.run_command(["git", "status", "--short"])
            has_changes = bool(status_output.strip())
            return ClientSuccess(
                data=has_changes,
                message=f"{'Has' if has_changes else 'No'} uncommitted changes"
            )
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="STATUS_CHECK_ERROR")

    def _get_upstream_status(self) -> Tuple[int, int]:
        """
        Get commits ahead/behind upstream.

        Returns:
            Tuple of (ahead, behind) counts
        """
        try:
            output = self.git.run_command(
                ["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"],
                check=False
            )
            if output:
                parts = output.split()
                if len(parts) == 2:
                    return int(parts[0]), int(parts[1])
        except GitCommandError:
            # No upstream configured
            pass
        return 0, 0
