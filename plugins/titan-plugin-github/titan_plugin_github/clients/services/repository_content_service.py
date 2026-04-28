"""Business logic for browsing repository contents through the GitHub contents API."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from titan_cli.core.logging import log_client_operation
from titan_cli.core.result import ClientError, ClientResult, ClientSuccess

from ..network import GHNetwork
from ...exceptions import GitHubAPIError


class RepositoryContentService:
    """Service for listing directories and checking remote repository paths."""

    def __init__(self, gh_network: GHNetwork):
        self.gh = gh_network

    @log_client_operation()
    def list_repository_directory(
        self,
        path: str,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        ref: Optional[str] = None,
    ) -> ClientResult[List[Dict[str, Any]]]:
        owner, repo = self._resolve_repo(repo_owner, repo_name)
        if not owner or not repo:
            return ClientError(
                error_message="Repository owner and name are required to list directory contents",
                error_code="CONFIG_ERROR",
            )

        normalized_path = path.strip("/")
        try:
            output = self.gh.run_command(self._build_contents_args(owner, repo, normalized_path, ref))
            data = json.loads(output)
        except (json.JSONDecodeError, TypeError) as exc:
            return ClientError(
                error_message=f"Failed to decode repository contents for '{normalized_path}': {exc}",
                error_code="PARSE_ERROR",
            )
        except GitHubAPIError as exc:
            return ClientError(
                error_message=f"Failed to list repository directory '{normalized_path}': {exc}",
                error_code="API_ERROR",
            )

        if not isinstance(data, list):
            return ClientError(
                error_message=f"Expected directory contents for '{normalized_path}', but GitHub returned a file",
                error_code="NOT_A_DIRECTORY",
            )

        return ClientSuccess(
            data=data,
            message=f"Listed {len(data)} entries from {owner}/{repo}:{normalized_path}",
        )

    @log_client_operation()
    def path_exists(
        self,
        path: str,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        ref: Optional[str] = None,
    ) -> ClientResult[bool]:
        owner, repo = self._resolve_repo(repo_owner, repo_name)
        if not owner or not repo:
            return ClientError(
                error_message="Repository owner and name are required to check path existence",
                error_code="CONFIG_ERROR",
            )

        normalized_path = path.strip("/")
        try:
            self.gh.run_command(self._build_contents_args(owner, repo, normalized_path, ref))
            return ClientSuccess(data=True, message=f"Path exists: {owner}/{repo}:{normalized_path}")
        except GitHubAPIError as exc:
            error_text = str(exc).lower()
            if "404" in error_text or "not found" in error_text:
                return ClientSuccess(data=False, message=f"Path not found: {owner}/{repo}:{normalized_path}")
            return ClientError(
                error_message=f"Failed to check repository path '{normalized_path}': {exc}",
                error_code="API_ERROR",
            )

    def _resolve_repo(self, repo_owner: Optional[str], repo_name: Optional[str]) -> tuple[str, str]:
        return repo_owner or self.gh.repo_owner, repo_name or self.gh.repo_name

    @staticmethod
    def _build_contents_args(owner: str, repo: str, path: str, ref: Optional[str]) -> list[str]:
        endpoint = f"repos/{owner}/{repo}/contents/{path}" if path else f"repos/{owner}/{repo}/contents"
        args = ["api", endpoint]
        if ref:
            args.extend(["-F", f"ref={ref}"])
        return args


__all__ = ["RepositoryContentService"]
