"""
Build Service - Business logic for managing builds.
"""

from typing import List, Optional
from pydantic import ValidationError

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..network.appstore_api import AppStoreConnectAPI
from ...models.network import BuildResponse
from ...models.view import BuildView
from ...models.mappers import NetworkToViewMapper
from ...exceptions import APIError, ResourceNotFoundError


class BuildService:
    """
    Service for managing builds in App Store Connect.

    Responsibilities:
    - List builds for a version
    - Get build details
    - Associate builds with versions
    """

    def __init__(self, api_client: AppStoreConnectAPI):
        """
        Initialize build service.

        Args:
            api_client: Low-level API client for HTTP requests
        """
        self.api = api_client

    def list_builds(
        self,
        app_id: str,
        version_id: Optional[str] = None,
        limit: int = 50,
    ) -> ClientResult[List[BuildView]]:
        """
        List builds for an app.

        Args:
            app_id: App ID from App Store Connect
            version_id: Optional version ID to filter builds
            limit: Maximum number of results

        Returns:
            ClientResult with list of BuildView models
        """
        try:
            query_params = {"limit": limit, "filter[app]": app_id}

            # Filter by version if provided
            if version_id:
                query_params["filter[appStoreVersion]"] = version_id

            # Only get non-expired, valid builds
            query_params["filter[expired]"] = "false"
            query_params["filter[processingState]"] = "VALID"

            # Sort by upload date (newest first)
            query_params["sort"] = "-uploadedDate"

            response_data = self.api.get("/builds", query_params=query_params)

            builds = response_data.get("data", [])

            # Parse to Network models
            network_builds = [BuildResponse(**build_data) for build_data in builds]

            # Map to View models
            view_builds = [NetworkToViewMapper.build_to_view(b) for b in network_builds]

            return ClientSuccess(
                data=view_builds,
                message=f"Found {len(view_builds)} build(s)"
            )

        except APIError as e:
            return ClientError(
                error_message=f"Failed to list builds: {str(e)}",
                error_code="API_ERROR"
            )
        except ValidationError as e:
            return ClientError(
                error_message=f"Failed to parse build data: {str(e)}",
                error_code="VALIDATION_ERROR"
            )

    def get_build(self, build_id: str) -> ClientResult[BuildView]:
        """
        Get details of a specific build.

        Args:
            build_id: Build ID

        Returns:
            ClientResult with BuildView model
        """
        try:
            response_data = self.api.get(f"/builds/{build_id}")

            build_data = response_data.get("data")
            if not build_data:
                return ClientError(
                    error_message=f"Build {build_id} not found",
                    error_code="NOT_FOUND",
                    log_level="warning"
                )

            # Parse to Network model
            network_build = BuildResponse(**build_data)

            # Map to View model
            view_build = NetworkToViewMapper.build_to_view(network_build)

            return ClientSuccess(
                data=view_build,
                message=f"Retrieved build {view_build.version}"
            )

        except APIError as e:
            if hasattr(e, 'status_code') and e.status_code == 404:
                return ClientError(
                    error_message=f"Build {build_id} not found",
                    error_code="NOT_FOUND",
                    log_level="warning"
                )
            return ClientError(
                error_message=f"Failed to get build: {str(e)}",
                error_code="API_ERROR"
            )
        except ValidationError as e:
            return ClientError(
                error_message=f"Failed to parse build data: {str(e)}",
                error_code="VALIDATION_ERROR"
            )
