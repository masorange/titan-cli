# plugins/titan-plugin-git/titan_plugin_git/clients/services/tag_service.py
"""
Tag Service

Business logic for Git tag operations.
Uses network layer to execute commands, parses to network models, maps to view models.
"""
from typing import List

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..network import GitNetwork
from ...models.network.tag import NetworkGitTag
from ...models.view.tag import UIGitTag
from ...models.mappers import from_network_tag
from ...exceptions import GitCommandError


class TagService:
    """
    Service for Git tag operations.

    Handles creating, deleting, and listing tags.
    Returns view models ready for UI rendering.
    """

    def __init__(self, git_network: GitNetwork):
        """
        Initialize Tag service.

        Args:
            git_network: GitNetwork instance for command execution
        """
        self.git = git_network

    def create_tag(
        self, tag_name: str, message: str, ref: str = "HEAD"
    ) -> ClientResult[None]:
        """
        Create an annotated tag.

        Args:
            tag_name: Name of the tag
            message: Tag annotation message
            ref: Reference to tag (default: HEAD)

        Returns:
            ClientResult[None]
        """
        try:
            self.git.run_command(["git", "tag", "-a", tag_name, "-m", message, ref])
            return ClientSuccess(data=None, message=f"Tag '{tag_name}' created")
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="TAG_CREATE_ERROR")

    def delete_tag(self, tag_name: str) -> ClientResult[None]:
        """
        Delete a local tag.

        Args:
            tag_name: Name of the tag to delete

        Returns:
            ClientResult[None]
        """
        try:
            self.git.run_command(["git", "tag", "-d", tag_name])
            return ClientSuccess(data=None, message=f"Tag '{tag_name}' deleted")
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="TAG_DELETE_ERROR")

    def tag_exists(self, tag_name: str) -> ClientResult[bool]:
        """
        Check if a tag exists locally.

        Args:
            tag_name: Name of the tag to check

        Returns:
            ClientResult[bool] with True if tag exists
        """
        try:
            tags = self.git.run_command(["git", "tag", "-l", tag_name], check=False)
            exists = tags.strip() == tag_name
            return ClientSuccess(
                data=exists,
                message=f"Tag '{tag_name}' {'exists' if exists else 'does not exist'}"
            )
        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="TAG_CHECK_ERROR")

    def list_tags(self) -> ClientResult[List[UIGitTag]]:
        """
        List all tags in the repository.

        Returns:
            ClientResult[List[UIGitTag]]
        """
        try:
            output = self.git.run_command(["git", "tag", "-l"])

            if not output.strip():
                return ClientSuccess(data=[], message="No tags found")

            tag_names = [tag.strip() for tag in output.split('\n') if tag.strip()]

            # Create network models and map to UI models
            network_tags = [NetworkGitTag(name=name) for name in tag_names]
            ui_tags = [from_network_tag(tag) for tag in network_tags]

            return ClientSuccess(
                data=ui_tags,
                message=f"Found {len(ui_tags)} tags"
            )

        except GitCommandError as e:
            return ClientError(error_message=str(e), error_code="TAG_LIST_ERROR")
