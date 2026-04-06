"""
Mappers to convert between network models (API DTOs) and view models (TUI).

These mappers ensure clean separation between API data structures
and user-facing display models.
"""

from typing import List
from .network import AppResponse, AppStoreVersionResponse, BuildResponse
from .view import AppView, VersionView, VersionSummaryView, BuildView


class NetworkToViewMapper:
    """
    Maps network models to view models.

    Handles data transformation from API responses to TUI-optimized models.
    """

    @staticmethod
    def app_to_view(app_response: AppResponse) -> AppView:
        """
        Convert App API response to view model.

        Args:
            app_response: Raw API response for an app

        Returns:
            AppView model for TUI display
        """
        return AppView(
            id=app_response.id,
            name=app_response.attributes.name,
            bundle_id=app_response.attributes.bundle_id,
            sku=app_response.attributes.sku,
            primary_locale=app_response.attributes.primary_locale,
        )

    @staticmethod
    def apps_to_view(app_responses: List[AppResponse]) -> List[AppView]:
        """
        Convert list of App responses to view models.

        Args:
            app_responses: List of raw API responses

        Returns:
            List of AppView models
        """
        return [NetworkToViewMapper.app_to_view(app) for app in app_responses]

    @staticmethod
    def version_to_view(version_response: AppStoreVersionResponse) -> VersionView:
        """
        Convert Version API response to full view model.

        Args:
            version_response: Raw API response for a version

        Returns:
            VersionView model with computed display fields
        """
        attrs = version_response.attributes

        view = VersionView(
            id=version_response.id,
            version_string=attrs.version_string,
            platform=attrs.platform,
            state=attrs.app_store_state,
            release_type=attrs.release_type,
            copyright=attrs.copyright,
            earliest_release_date=attrs.earliest_release_date,
            created_date=attrs.created_date,
            downloadable=attrs.downloadable or False,
        )

        # Compute display fields
        view.state_display = view.format_state()
        view.platform_display = view.format_platform()
        view.release_type_display = view.format_release_type()

        return view

    @staticmethod
    def versions_to_view(version_responses: List[AppStoreVersionResponse]) -> List[VersionView]:
        """
        Convert list of Version responses to view models.

        Args:
            version_responses: List of raw API responses

        Returns:
            List of VersionView models
        """
        return [NetworkToViewMapper.version_to_view(v) for v in version_responses]

    @staticmethod
    def version_to_summary(version_response: AppStoreVersionResponse) -> VersionSummaryView:
        """
        Convert Version API response to summary view model.

        Used for compact list displays.

        Args:
            version_response: Raw API response for a version

        Returns:
            VersionSummaryView model for compact display
        """
        attrs = version_response.attributes

        return VersionSummaryView(
            id=version_response.id,
            version_string=attrs.version_string,
            state=attrs.app_store_state,
            platform=attrs.platform,
            created_date=attrs.created_date,
        )

    @staticmethod
    def versions_to_summary(
        version_responses: List[AppStoreVersionResponse]
    ) -> List[VersionSummaryView]:
        """
        Convert list of Version responses to summary view models.

        Args:
            version_responses: List of raw API responses

        Returns:
            List of VersionSummaryView models
        """
        return [NetworkToViewMapper.version_to_summary(v) for v in version_responses]

    @staticmethod
    def build_to_view(build_response: BuildResponse) -> BuildView:
        """
        Convert Build API response to view model.

        Args:
            build_response: Raw API response for a build

        Returns:
            BuildView model for TUI display
        """
        attrs = build_response.attributes

        return BuildView(
            id=build_response.id,
            version=attrs.version,
            uploaded_date=attrs.uploaded_date,
            processing_state=attrs.processing_state,
            expired=attrs.expired or False,
        )

    @staticmethod
    def builds_to_view(build_responses: List[BuildResponse]) -> List[BuildView]:
        """
        Convert list of Build responses to view models.

        Args:
            build_responses: List of raw API responses

        Returns:
            List of BuildView models
        """
        return [NetworkToViewMapper.build_to_view(b) for b in build_responses]
