"""
App Service - Business logic for managing apps.
"""

from typing import List, Optional
from pydantic import ValidationError

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..network.appstore_api import AppStoreConnectAPI
from ...models.network import AppResponse
from ...models.view import AppView
from ...models.mappers import NetworkToViewMapper
from ...exceptions import APIError, ResourceNotFoundError


class AppService:
    """
    Service for managing apps in App Store Connect.

    Responsibilities:
    - List apps with filters
    - Retrieve specific app details
    - Convert API responses to domain models
    """

    def __init__(self, api_client: AppStoreConnectAPI):
        """
        Initialize app service.

        Args:
            api_client: Low-level API client for HTTP requests
        """
        self.api = api_client

    def list_apps(
        self, filter_bundle_id: Optional[str] = None, limit: int = 200
    ) -> ClientResult[List[AppView]]:
        """
        List all apps in App Store Connect.

        Args:
            filter_bundle_id: Optional bundle ID filter
            limit: Maximum number of results

        Returns:
            ClientResult with list of AppView models
        """
        try:
            query_params = {"limit": limit}
            if filter_bundle_id:
                query_params["filter[bundleId]"] = filter_bundle_id

            response_data = self.api.get("/apps", query_params=query_params)

            # Parse response data
            apps = response_data.get("data", [])

            # Convert to Network models
            network_apps = [AppResponse(**app_data) for app_data in apps]

            # Map to View models
            view_apps = NetworkToViewMapper.apps_to_view(network_apps)

            return ClientSuccess(
                data=view_apps,
                message=f"Found {len(view_apps)} app(s)"
            )

        except APIError as e:
            return ClientError(
                error_message=f"Failed to list apps: {str(e)}",
                error_code="API_ERROR"
            )
        except ValidationError as e:
            return ClientError(
                error_message=f"Failed to parse app data: {str(e)}",
                error_code="VALIDATION_ERROR"
            )

    def get_app(self, app_id: str) -> ClientResult[AppView]:
        """
        Get details of a specific app.

        Args:
            app_id: App ID from App Store Connect

        Returns:
            ClientResult with AppView model
        """
        try:
            response_data = self.api.get(f"/apps/{app_id}")
            app_data = response_data.get("data", {})

            # Convert to Network model
            network_app = AppResponse(**app_data)

            # Map to View model
            view_app = NetworkToViewMapper.app_to_view(network_app)

            return ClientSuccess(
                data=view_app,
                message=f"Retrieved app {view_app.name}"
            )

        except APIError as e:
            if hasattr(e, 'status_code') and e.status_code == 404:
                return ClientError(
                    error_message=f"App with ID {app_id} not found",
                    error_code="NOT_FOUND",
                    log_level="warning"
                )
            return ClientError(
                error_message=f"Failed to get app: {str(e)}",
                error_code="API_ERROR"
            )
        except ValidationError as e:
            return ClientError(
                error_message=f"Failed to parse app data: {str(e)}",
                error_code="VALIDATION_ERROR"
            )

    def find_app_by_bundle_id(self, bundle_id: str) -> ClientResult[Optional[AppView]]:
        """
        Find an app by bundle ID.

        Args:
            bundle_id: Bundle ID to search for

        Returns:
            ClientResult with AppView if found, None otherwise
        """
        result = self.list_apps(filter_bundle_id=bundle_id, limit=1)

        match result:
            case ClientSuccess(data=apps):
                app = apps[0] if apps else None
                return ClientSuccess(
                    data=app,
                    message=f"Found app for {bundle_id}" if app else f"No app found for {bundle_id}"
                )
            case ClientError() as error:
                return error
