# plugins/titan-plugin-github/titan_plugin_github/clients/services/release_service.py
"""
Release Service

Business logic for GitHub release operations.
Uses gh CLI through the network layer.
"""

import json
from typing import Optional

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError
from titan_cli.core.logging import log_client_operation

from ..network import GHNetwork
from ...exceptions import GitHubAPIError
from ...models.network.rest import NetworkRelease
from ...models.view import UIRelease
from ...models.mappers import from_network_release


class ReleaseService:
    """
    Service for GitHub release operations.

    Handles creating GitHub releases for a repository.
    """

    def __init__(self, gh_network: GHNetwork):
        """
        Initialize release service.

        Args:
            gh_network: GHNetwork instance for REST/CLI operations
        """
        self.gh = gh_network

    @log_client_operation()
    def create_release(
        self,
        tag_name: str,
        title: Optional[str] = None,
        notes: Optional[str] = None,
        generate_notes: bool = False,
        verify_tag: bool = True,
        prerelease: bool = False,
    ) -> ClientResult[UIRelease]:
        """
        Create a GitHub release and return a UI release model.

        Args:
            tag_name: Tag to publish
            title: Release title
            notes: Optional release notes body
            generate_notes: Ask GitHub to generate release notes
            verify_tag: Require tag to exist remotely
            prerelease: Mark release as prerelease

        Returns:
            ClientResult[UIRelease]
        """
        if notes and generate_notes:
            return ClientError(
                error_message="Specify either notes or generate_notes, not both",
                error_code="INVALID_INPUT",
            )

        try:
            args = ["release", "create", tag_name]

            if title:
                args.extend(["--title", title])

            if notes:
                args.extend(["--notes", notes])
            elif generate_notes:
                args.append("--generate-notes")

            if verify_tag:
                args.append("--verify-tag")

            if prerelease:
                args.append("--prerelease")

            args.extend(self.gh.get_repo_arg())

            self.gh.run_command(args)

            view_args = [
                "release", "view", tag_name,
                "--json", "tagName,name,url,isPrerelease",
            ] + self.gh.get_repo_arg()

            output = self.gh.run_command(view_args)
            data = json.loads(output)
            network_release = NetworkRelease.from_json(data)
            ui_release = from_network_release(network_release)

            return ClientSuccess(
                data=ui_release,
                message=f"Release '{tag_name}' created"
            )

        except json.JSONDecodeError as e:
            return ClientError(
                error_message=f"Failed to parse release data: {e}",
                error_code="JSON_PARSE_ERROR"
            )
        except GitHubAPIError as e:
            return ClientError(error_message=str(e), error_code="API_ERROR")
