# plugins/titan-plugin-git/titan_plugin_git/clients/services/stash_service.py
"""
Stash Service

Business logic for Git stash operations.
Uses network layer to execute commands for stash push, pop, and search.
"""
from datetime import datetime
from typing import List, Optional

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError
from titan_cli.core.logging import log_client_operation

from ..network import GitNetwork
from ...models.mappers import from_network_stash
from ...models.network import NetworkGitStash
from ...models.view import UIGitStash
from ...exceptions import GitCommandError
from ...messages import msg


class StashService:
    """
    Service for Git stash operations.

    Handles stashing, popping, and finding stashes.
    """

    def __init__(self, git_network: GitNetwork):
        """
        Initialize Stash service.

        Args:
            git_network: GitNetwork instance for command execution
        """
        self.git = git_network

    @log_client_operation()
    def stash_push(self, message: Optional[str] = None, include_untracked: bool = False) -> ClientResult[bool]:
        """
        Stash uncommitted changes.

        Args:
            message: Optional stash message
            include_untracked: Also stash new, untracked files (not ignored ones), so the
                tree ends up clean

        Returns:
            ClientResult[bool] with True if stash was created
        """
        if not message:
            message = msg.Git.AUTO_STASH_MESSAGE.format(
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

        try:
            args = ["git", "stash", "push", *(["--include-untracked"] if include_untracked else []), "-m", message]
            self.git.run_command(args)
            return ClientSuccess(data=True, message=f"Stashed with message: {message}")
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="STASH_ERROR")

    @log_client_operation()
    def stash_pop(self, stash_ref: Optional[str] = None) -> ClientResult[bool]:
        """
        Pop stash (apply and remove).

        Args:
            stash_ref: Optional stash reference (default: latest)

        Returns:
            ClientResult[bool] with True if stash was applied successfully
        """
        try:
            args = ["git", "stash", "pop"]
            if stash_ref:
                args.append(stash_ref)

            self.git.run_command(args)
            return ClientSuccess(data=True, message="Stash popped successfully")
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="STASH_POP_ERROR")

    @log_client_operation()
    def list_stashes(self) -> ClientResult[List[UIGitStash]]:
        """
        List the stashes, newest first.

        Returns:
            ClientResult[List[UIGitStash]]
        """
        try:
            output = self.git.run_command(["git", "stash", "list", "--format=%gd%x1f%gs%x1f%cr"])
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="STASH_LIST_ERROR")

        stashes = []
        for line in output.splitlines():
            ref, _, rest = line.partition("\x1f")
            subject, _, date = rest.partition("\x1f")
            if ref:
                stashes.append(from_network_stash(NetworkGitStash(ref=ref, subject=subject, relative_date=date)))
        return ClientSuccess(data=stashes, message=f"{len(stashes)} stashes")

    @log_client_operation()
    def find_stash_by_message(self, message: str) -> ClientResult[Optional[str]]:
        """
        Find stash by message.

        Args:
            message: Stash message to search for

        Returns:
            ClientResult[Optional[str]] with stash reference (e.g., "stash@{0}") or None
        """
        try:
            output = self.git.run_command(["git", "stash", "list"])

            for line in output.splitlines():
                if message in line:
                    stash_ref = line.split(':')[0].strip()
                    return ClientSuccess(
                        data=stash_ref,
                        message=f"Found stash: {stash_ref}"
                    )

            return ClientSuccess(data=None, message="Stash not found")

        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="STASH_FIND_ERROR")

    @log_client_operation()
    def restore_stash(self, message: str) -> ClientResult[bool]:
        """
        Restore stash by finding it with a message and popping it.

        Args:
            message: Stash message to search for

        Returns:
            ClientResult[bool] with True if stash was restored successfully
        """
        # Find stash
        find_result = self.find_stash_by_message(message)

        match find_result:
            case ClientSuccess(data=stash_ref) if stash_ref:
                # Pop the stash
                pop_result = self.stash_pop(stash_ref)
                match pop_result:
                    case ClientSuccess():
                        return ClientSuccess(
                            data=True,
                            message=f"Restored stash: {stash_ref}"
                        )
                    case ClientError() as err:
                        return err
            case ClientSuccess(data=None):
                return ClientSuccess(data=False, message="No stash to restore")
            case ClientError() as err:
                return err

        return ClientSuccess(data=False, message="Failed to restore stash")
