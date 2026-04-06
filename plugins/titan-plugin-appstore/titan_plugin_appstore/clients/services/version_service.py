"""
Version Service - Business logic for managing app versions.
"""

from typing import List, Optional
from pydantic import ValidationError

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..network.appstore_api import AppStoreConnectAPI
from ...models.network import AppStoreVersionResponse
from ...models.view import VersionView
from ...models.mappers import NetworkToViewMapper
from ...exceptions import APIError, ResourceNotFoundError, VersionConflictError


class VersionService:
    """
    Service for managing app versions in App Store Connect.

    Responsibilities:
    - List versions for an app
    - Create new versions
    - Update existing versions
    - Delete versions
    - Version conflict detection
    """

    def __init__(self, api_client: AppStoreConnectAPI):
        """
        Initialize version service.

        Args:
            api_client: Low-level API client for HTTP requests
        """
        self.api = api_client

    def list_versions(
        self,
        app_id: str,
        platform: str = "IOS",
        version_string: Optional[str] = None,
        limit: int = 50,
    ) -> List[AppStoreVersionResponse]:
        """
        List versions for an app.

        Args:
            app_id: App ID from App Store Connect
            platform: Platform filter (IOS, MAC_OS, TV_OS)
            version_string: Optional version string filter
            limit: Maximum number of results

        Returns:
            List of AppStoreVersionResponse models

        Raises:
            APIError: If API request fails
        """
        query_params = {"limit": limit}

        if platform:
            query_params["filter[platform]"] = platform
        if version_string:
            query_params["filter[versionString]"] = version_string

        response_data = self.api.get(f"/apps/{app_id}/appStoreVersions", query_params=query_params)

        versions = response_data.get("data", [])

        try:
            return [AppStoreVersionResponse(**version_data) for version_data in versions]
        except ValidationError as e:
            raise APIError(f"Failed to parse version data: {e}")

    def get_version(self, version_id: str) -> AppStoreVersionResponse:
        """
        Get details of a specific version.

        Args:
            version_id: App Store Version ID

        Returns:
            AppStoreVersionResponse model

        Raises:
            ResourceNotFoundError: If version not found
            APIError: If API request fails
        """
        try:
            response_data = self.api.get(f"/appStoreVersions/{version_id}")
        except APIError as e:
            if e.status_code == 404:
                raise ResourceNotFoundError(f"Version with ID {version_id} not found")
            raise

        version_data = response_data.get("data", {})

        try:
            return AppStoreVersionResponse(**version_data)
        except ValidationError as e:
            raise APIError(f"Failed to parse version data: {e}")

    def create_version(
        self,
        app_id: str,
        version_string: str,
        platform: str = "IOS",
        copyright: Optional[str] = None,
        earliest_release_date: Optional[str] = None,
        release_type: str = "MANUAL",
    ) -> ClientResult[VersionView]:
        """
        Create a new app version.

        Args:
            app_id: App ID from App Store Connect
            version_string: Version number (e.g., "1.2.3")
            platform: Platform (IOS, MAC_OS, TV_OS)
            copyright: Copyright text
            earliest_release_date: ISO 8601 date string
            release_type: MANUAL, AFTER_APPROVAL, or SCHEDULED

        Returns:
            ClientResult with created VersionView model
        """
        try:
            # Check if version already exists
            existing_result = self.list_versions(app_id, platform=platform, version_string=version_string)

            match existing_result:
                case ClientSuccess(data=versions):
                    if versions:
                        return ClientError(
                            error_message=f"Version {version_string} already exists for platform {platform}",
                            error_code="VERSION_CONFLICT",
                            log_level="warning"
                        )
                case ClientError() as error:
                    return error

            # Build request payload
            payload = {
                "data": {
                    "type": "appStoreVersions",
                    "attributes": {
                        "platform": platform,
                        "versionString": version_string,
                        "releaseType": release_type,
                    },
                    "relationships": {"app": {"data": {"type": "apps", "id": app_id}}},
                }
            }

            # Add optional attributes
            if copyright:
                payload["data"]["attributes"]["copyright"] = copyright
            if earliest_release_date:
                payload["data"]["attributes"]["earliestReleaseDate"] = earliest_release_date

            response_data = self.api.post("/appStoreVersions", json_data=payload)
            version_data = response_data.get("data", {})

            # Parse to Network model
            network_version = AppStoreVersionResponse(**version_data)

            # Map to View model
            view_version = NetworkToViewMapper.version_to_view(network_version)

            return ClientSuccess(
                data=view_version,
                message=f"Created version {view_version.version_string}"
            )

        except APIError as e:
            if hasattr(e, 'status_code') and e.status_code == 409:
                return ClientError(
                    error_message=f"Version {version_string} already exists",
                    error_code="VERSION_CONFLICT",
                    log_level="warning"
                )
            return ClientError(
                error_message=f"Failed to create version: {str(e)}",
                error_code="API_ERROR"
            )
        except ValidationError as e:
            return ClientError(
                error_message=f"Failed to parse created version data: {str(e)}",
                error_code="VALIDATION_ERROR"
            )

    def update_version(
        self,
        version_id: str,
        version_string: Optional[str] = None,
        copyright: Optional[str] = None,
        release_type: Optional[str] = None,
        earliest_release_date: Optional[str] = None,
    ) -> ClientResult[VersionView]:
        """
        Update an existing version.

        Args:
            version_id: App Store Version ID
            version_string: New version number
            copyright: Copyright text
            release_type: MANUAL, AFTER_APPROVAL, or SCHEDULED
            earliest_release_date: ISO 8601 date string

        Returns:
            ClientResult with updated VersionView model
        """
        try:
            payload = {"data": {"type": "appStoreVersions", "id": version_id, "attributes": {}}}

            # Add only provided attributes
            if version_string is not None:
                payload["data"]["attributes"]["versionString"] = version_string
            if copyright is not None:
                payload["data"]["attributes"]["copyright"] = copyright
            if release_type is not None:
                payload["data"]["attributes"]["releaseType"] = release_type
            if earliest_release_date is not None:
                payload["data"]["attributes"]["earliestReleaseDate"] = earliest_release_date

            response_data = self.api.patch(f"/appStoreVersions/{version_id}", json_data=payload)
            version_data = response_data.get("data", {})

            # Parse to Network model
            network_version = AppStoreVersionResponse(**version_data)

            # Map to View model
            view_version = NetworkToViewMapper.version_to_view(network_version)

            return ClientSuccess(
                data=view_version,
                message=f"Updated version {view_version.version_string}"
            )

        except APIError as e:
            if hasattr(e, 'status_code') and e.status_code == 404:
                return ClientError(
                    error_message=f"Version with ID {version_id} not found",
                    error_code="NOT_FOUND",
                    log_level="warning"
                )
            return ClientError(
                error_message=f"Failed to update version: {str(e)}",
                error_code="API_ERROR"
            )
        except ValidationError as e:
            return ClientError(
                error_message=f"Failed to parse updated version data: {str(e)}",
                error_code="VALIDATION_ERROR"
            )

    def delete_version(self, version_id: str) -> ClientResult[bool]:
        """
        Delete an app version.

        Args:
            version_id: App Store Version ID

        Returns:
            ClientResult with True if successful
        """
        try:
            self.api.delete(f"/appStoreVersions/{version_id}")

            return ClientSuccess(
                data=True,
                message=f"Deleted version {version_id}"
            )

        except APIError as e:
            if hasattr(e, 'status_code') and e.status_code == 404:
                return ClientError(
                    error_message=f"Version with ID {version_id} not found",
                    error_code="NOT_FOUND",
                    log_level="warning"
                )
            return ClientError(
                error_message=f"Failed to delete version: {str(e)}",
                error_code="API_ERROR"
            )

    def version_exists(self, app_id: str, version_string: str, platform: str = "IOS") -> ClientResult[bool]:
        """
        Check if a version already exists.

        Args:
            app_id: App ID
            version_string: Version to check
            platform: Platform filter

        Returns:
            ClientResult with True if version exists, False otherwise
        """
        result = self.list_versions(app_id, platform=platform, version_string=version_string)

        match result:
            case ClientSuccess(data=versions):
                exists = len(versions) > 0
                return ClientSuccess(
                    data=exists,
                    message=f"Version {version_string} {'exists' if exists else 'does not exist'}"
                )
            case ClientError() as error:
                return error
