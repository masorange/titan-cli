"""
App Store Connect Client - Public Facade

This is the main entry point for interacting with App Store Connect.
Combines all services into a single, easy-to-use interface.
"""

from typing import List, Optional, Union

from titan_cli.core.result import ClientResult, ClientSuccess, ClientError

from .network.appstore_api import AppStoreConnectAPI
from .services.app_service import AppService
from .services.version_service import VersionService
from .services.build_service import BuildService
from .services.submission_service import SubmissionService
from .services.metrics_service import MetricsService
from ..models.view import AppView, VersionView, BuildView, VersionCreationRequest, VersionSummaryView
from ..models.mappers import NetworkToViewMapper
from ..exceptions import ConfigurationError


class AppStoreConnectClient:
    """
    High-level client for App Store Connect.

    This facade provides a clean, user-friendly API that:
    - Handles authentication
    - Delegates to specialized services
    - Returns ClientResult[ViewModel] consistently
    """

    def __init__(
        self,
        key_id: str,
        issuer_id: Optional[str] = None,
        private_key_path: Optional[str] = None,
        private_key_content: Optional[str] = None,
    ):
        """
        Initialize App Store Connect client.

        Args:
            key_id: Key ID from App Store Connect
            issuer_id: Issuer ID (None for Individual Keys)
            private_key_path: Path to .p8 private key file
            private_key_content: Content of .p8 private key

        Raises:
            ConfigurationError: If credentials are invalid
        """
        try:
            # Initialize low-level API client
            self._api = AppStoreConnectAPI(
                key_id=key_id,
                issuer_id=issuer_id,
                private_key_path=private_key_path,
                private_key_content=private_key_content,
            )

            # Initialize services
            self._app_service = AppService(self._api)
            self._version_service = VersionService(self._api)
            self._build_service = BuildService(self._api)
            self._submission_service = SubmissionService(self._api)
            self.metrics = MetricsService(self._api)

        except Exception as e:
            raise ConfigurationError(f"Failed to initialize client: {e}")

    @classmethod
    def from_credentials_file(cls, credentials_path: str) -> "AppStoreConnectClient":
        """
        Create client from credentials file.

        Args:
            credentials_path: Path to JSON credentials file

        Returns:
            Initialized client

        Raises:
            ConfigurationError: If credentials file is invalid
        """
        import json

        try:
            with open(credentials_path, "r") as f:
                creds = json.load(f)

            return cls(
                key_id=creds.get("key_id"),
                issuer_id=creds.get("issuer_id"),
                private_key_path=creds.get("p8_file_path"),
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to load credentials: {e}")

    # ==================== App Operations ====================

    def list_apps(self, bundle_id_filter: Optional[str] = None) -> ClientResult[List[AppView]]:
        """List all apps."""
        return self._app_service.list_apps(filter_bundle_id=bundle_id_filter)

    def get_app(self, app_id: str) -> ClientResult[AppView]:
        """Get app details."""
        return self._app_service.get_app(app_id)

    def find_app_by_bundle_id(self, bundle_id: str) -> ClientResult[Optional[AppView]]:
        """Find app by bundle ID."""
        return self._app_service.find_app_by_bundle_id(bundle_id)

    # ==================== Version Operations ====================

    def list_versions(
        self,
        app_id: str,
        platform: str = "IOS",
        as_summary: bool = False,
        limit: int = 50,
        version_string: Optional[str] = None,
    ) -> ClientResult[List[Union[VersionView, VersionSummaryView]]]:
        """
        List versions for an app (returns ClientResult).

        Args:
            app_id: App ID
            platform: Platform filter
            as_summary: Return summary models (for compact display)
            limit: Maximum number of versions to return
            version_string: Optional version string filter

        Returns:
            ClientResult[List[VersionView | VersionSummaryView]]
        """
        try:
            version_responses = self._version_service.list_versions(
                app_id, platform=platform, limit=limit, version_string=version_string
            )

            if as_summary:
                versions = NetworkToViewMapper.versions_to_summary(version_responses)
            else:
                versions = NetworkToViewMapper.versions_to_view(version_responses)

            return ClientSuccess(versions)
        except Exception as e:
            return ClientError(f"Failed to list versions: {str(e)}")

    def get_version(self, version_id: str) -> ClientResult[VersionView]:
        """
        Get version details (returns ClientResult).

        Args:
            version_id: Version ID

        Returns:
            ClientResult[VersionView]
        """
        try:
            version_response = self._version_service.get_version(version_id)
            version = NetworkToViewMapper.version_to_view(version_response)
            return ClientSuccess(data=version, message=f"Retrieved version {version_id}")
        except Exception as e:
            return ClientError(
                error_message=f"Failed to get version: {str(e)}",
                error_code="VERSION_GET_ERROR",
            )

    def create_version(self, request: VersionCreationRequest) -> ClientResult[VersionView]:
        """
        Create a new version.

        Args:
            request: Version creation request model

        Returns:
            ClientResult[VersionView]
        """
        # Validate version format
        if not request.validate_version_format():
            return ClientError(
                error_message=f"Invalid version format: {request.version_string}. "
                "Expected format: MAJOR.MINOR[.PATCH][.BUILD] (e.g., 1.2.3)",
                error_code="VALIDATION_ERROR",
            )

        return self._version_service.create_version(
            app_id=request.app_id,
            version_string=request.version_string,
            platform=request.platform,
            copyright=request.copyright,
            earliest_release_date=request.earliest_release_date,
            release_type=request.release_type,
        )

    def version_exists(self, app_id: str, version_string: str, platform: str = "IOS") -> ClientResult[bool]:
        """Check if version exists."""
        return self._version_service.version_exists(app_id, version_string, platform)

    def delete_version(self, version_id: str) -> ClientResult[bool]:
        """Delete a version."""
        return self._version_service.delete_version(version_id)

    # ==================== Build Operations ====================

    def list_builds(
        self, app_id: str, version_id: Optional[str] = None
    ) -> ClientResult[List[BuildView]]:
        """List builds for an app."""
        return self._build_service.list_builds(app_id, version_id)

    def get_build(self, build_id: str) -> ClientResult[BuildView]:
        """Get build details."""
        return self._build_service.get_build(build_id)

    # ==================== Submission Operations ====================

    def update_whats_new(
        self, version_id: str, locale: str, whats_new_text: str
    ) -> ClientResult[bool]:
        """Update What's New text for a version localization."""
        return self._submission_service.update_whats_new(
            version_id, locale, whats_new_text
        )

    def assign_build_to_version(
        self, version_id: str, build_id: str
    ) -> ClientResult[bool]:
        """Assign a build to a version."""
        return self._submission_service.assign_build_to_version(version_id, build_id)

    def submit_for_review(self, version_id: str) -> ClientResult[bool]:
        """Submit a version for App Store review."""
        return self._submission_service.submit_for_review(version_id)

    # ==================== Convenience Methods ====================

    def test_connection(self) -> ClientResult[bool]:
        """
        Test API connection by listing apps.

        Returns:
            ClientResult[bool]
        """
        result = self._app_service.list_apps(limit=1)

        match result:
            case ClientSuccess():
                return ClientSuccess(data=True, message="Connection successful")
            case ClientError() as error:
                return ClientError(
                    error_message=f"Connection failed: {error.error_message}",
                    error_code="CONNECTION_ERROR",
                )

    def get_latest_version(self, app_id: str, platform: str = "IOS") -> ClientResult[Optional[VersionView]]:
        """
        Get the latest version for an app.

        Args:
            app_id: App ID
            platform: Platform filter

        Returns:
            ClientResult[Optional[VersionView]]
        """
        versions_result = self.list_versions(app_id, platform=platform)

        match versions_result:
            case ClientSuccess(data=versions):
                if not versions:
                    return ClientSuccess(data=None, message="No versions found")

                # Sort by created date (newest first)
                sorted_versions = sorted(
                    versions, key=lambda v: v.created_date or "", reverse=True
                )
                return ClientSuccess(
                    data=sorted_versions[0],
                    message=f"Latest version: {sorted_versions[0].version_string}",
                )
            case ClientError() as err:
                return err
