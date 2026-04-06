"""
Submission Service - Business logic for version submissions and localizations.
"""

from typing import List, Dict, Any
from pydantic import ValidationError, BaseModel

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from ..network.appstore_api import AppStoreConnectAPI
from ...models.network import LocalizationResponse
from ...exceptions import APIError, ResourceNotFoundError


class LocalizationView(BaseModel):
    """Simple view model for localizations."""
    id: str
    locale: str
    whats_new: str = ""
    description: str = ""


class SubmissionService:
    """
    Service for managing version submissions and localizations.

    Responsibilities:
    - Update version localizations (What's New text)
    - Submit versions for review
    - Manage version metadata
    """

    def __init__(self, api_client: AppStoreConnectAPI):
        """
        Initialize submission service.

        Args:
            api_client: Low-level API client for HTTP requests
        """
        self.api = api_client

    def list_localizations(self, version_id: str) -> ClientResult[List[LocalizationView]]:
        """
        List localizations for a version.

        Args:
            version_id: App Store Version ID

        Returns:
            ClientResult with list of LocalizationView models
        """
        try:
            response_data = self.api.get(
                f"/appStoreVersions/{version_id}/appStoreVersionLocalizations"
            )

            localizations = response_data.get("data", [])

            # Parse to Network models
            network_locs = [LocalizationResponse(**loc_data) for loc_data in localizations]

            # Map to simple View models
            view_locs = [
                LocalizationView(
                    id=loc.id,
                    locale=loc.attributes.locale,
                    whats_new=loc.attributes.whats_new or "",
                    description=loc.attributes.description or ""
                )
                for loc in network_locs
            ]

            return ClientSuccess(
                data=view_locs,
                message=f"Found {len(view_locs)} localization(s)"
            )

        except APIError as e:
            return ClientError(
                error_message=f"Failed to list localizations: {str(e)}",
                error_code="API_ERROR"
            )
        except ValidationError as e:
            return ClientError(
                error_message=f"Failed to parse localization data: {str(e)}",
                error_code="VALIDATION_ERROR"
            )

    def get_or_create_localization(
        self, version_id: str, locale: str
    ) -> ClientResult[LocalizationView]:
        """
        Get or create a localization for a version.

        If the localization exists, returns it. Otherwise creates it.

        Args:
            version_id: App Store Version ID
            locale: Locale code (e.g., "es-ES", "en-US")

        Returns:
            ClientResult with LocalizationView model
        """
        try:
            # First, try to find existing localization
            locs_result = self.list_localizations(version_id)

            match locs_result:
                case ClientSuccess(data=localizations):
                    for loc in localizations:
                        if loc.locale == locale:
                            return ClientSuccess(
                                data=loc,
                                message=f"Found existing localization for {locale}"
                            )
                case ClientError() as error:
                    return error

            # If not found, create it
            payload = {
                "data": {
                    "type": "appStoreVersionLocalizations",
                    "attributes": {"locale": locale},
                    "relationships": {
                        "appStoreVersion": {
                            "data": {"type": "appStoreVersions", "id": version_id}
                        }
                    },
                }
            }

            response_data = self.api.post("/appStoreVersionLocalizations", json_data=payload)

            loc_data = response_data.get("data")
            if not loc_data:
                return ClientError(
                    error_message="Failed to create localization",
                    error_code="API_ERROR"
                )

            # Parse to Network model
            network_loc = LocalizationResponse(**loc_data)

            # Map to View model
            view_loc = LocalizationView(
                id=network_loc.id,
                locale=network_loc.attributes.locale,
                whats_new=network_loc.attributes.whats_new or "",
                description=network_loc.attributes.description or ""
            )

            return ClientSuccess(
                data=view_loc,
                message=f"Created localization for {locale}"
            )

        except APIError as e:
            return ClientError(
                error_message=f"Failed to get or create localization: {str(e)}",
                error_code="API_ERROR"
            )
        except ValidationError as e:
            return ClientError(
                error_message=f"Failed to parse localization data: {str(e)}",
                error_code="VALIDATION_ERROR"
            )

    def update_whats_new(
        self, version_id: str, locale: str, whats_new_text: str
    ) -> ClientResult[LocalizationView]:
        """
        Update What's New text for a version localization.

        Args:
            version_id: App Store Version ID
            locale: Locale code (e.g., "es-ES", "en-US")
            whats_new_text: What's New text (max 4000 characters)

        Returns:
            ClientResult with updated LocalizationView model
        """
        try:
            # Get or create the localization
            loc_result = self.get_or_create_localization(version_id, locale)

            match loc_result:
                case ClientSuccess(data=localization):
                    pass
                case ClientError() as error:
                    return error

            # Update the What's New text
            payload = {
                "data": {
                    "type": "appStoreVersionLocalizations",
                    "id": localization.id,
                    "attributes": {"whatsNew": whats_new_text},
                }
            }

            response_data = self.api.patch(
                f"/appStoreVersionLocalizations/{localization.id}", json_data=payload
            )

            loc_data = response_data.get("data")
            if not loc_data:
                return ClientError(
                    error_message="Failed to update What's New text",
                    error_code="API_ERROR"
                )

            # Parse to Network model
            network_loc = LocalizationResponse(**loc_data)

            # Map to View model
            view_loc = LocalizationView(
                id=network_loc.id,
                locale=network_loc.attributes.locale,
                whats_new=network_loc.attributes.whats_new or "",
                description=network_loc.attributes.description or ""
            )

            return ClientSuccess(
                data=view_loc,
                message=f"Updated What's New for {locale}"
            )

        except APIError as e:
            return ClientError(
                error_message=f"Failed to update What's New: {str(e)}",
                error_code="API_ERROR"
            )
        except ValidationError as e:
            return ClientError(
                error_message=f"Failed to parse localization data: {str(e)}",
                error_code="VALIDATION_ERROR"
            )

    def assign_build_to_version(self, version_id: str, build_id: str) -> ClientResult[bool]:
        """
        Assign a build to a version.

        Args:
            version_id: App Store Version ID
            build_id: Build ID

        Returns:
            ClientResult with True if successful
        """
        try:
            payload = {
                "data": {
                    "type": "appStoreVersions",
                    "id": version_id,
                    "relationships": {
                        "build": {"data": {"type": "builds", "id": build_id}}
                    },
                }
            }

            self.api.patch(
                f"/appStoreVersions/{version_id}", json_data=payload
            )

            return ClientSuccess(
                data=True,
                message=f"Assigned build {build_id} to version {version_id}"
            )

        except APIError as e:
            return ClientError(
                error_message=f"Failed to assign build: {str(e)}",
                error_code="API_ERROR"
            )

    def submit_for_review(self, version_id: str) -> ClientResult[bool]:
        """
        Submit a version for App Store review.

        The version must have:
        - A build assigned
        - All required metadata filled
        - All localizations complete

        Args:
            version_id: App Store Version ID

        Returns:
            ClientResult with True if successful
        """
        try:
            # Create a submission resource
            payload = {
                "data": {
                    "type": "appStoreVersionSubmissions",
                    "relationships": {
                        "appStoreVersion": {
                            "data": {"type": "appStoreVersions", "id": version_id}
                        }
                    },
                }
            }

            response_data = self.api.post("/appStoreVersionSubmissions", json_data=payload)

            if not response_data.get("data"):
                return ClientError(
                    error_message="Failed to submit version for review",
                    error_code="API_ERROR"
                )

            return ClientSuccess(
                data=True,
                message=f"Submitted version {version_id} for review"
            )

        except APIError as e:
            return ClientError(
                error_message=f"Failed to submit for review: {str(e)}",
                error_code="API_ERROR"
            )
