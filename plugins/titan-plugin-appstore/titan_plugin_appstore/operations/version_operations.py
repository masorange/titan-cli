"""
Version Operations - Complex business workflows for versions.

Orchestrates multiple API calls and provides high-level operations.
"""

from typing import List, Optional, Tuple
from datetime import datetime
from titan_cli.core.result import ClientSuccess, ClientError
from ..clients.appstore_client import AppStoreConnectClient
from ..models.view import VersionView, VersionSummaryView, VersionCreationRequest
from ..exceptions import ValidationError, VersionConflictError


class VersionOperations:
    """
    High-level operations for version management.

    Responsibilities:
    - Version creation with validation and conflict handling
    - Bulk operations
    - Version comparison and analysis
    - Workflow orchestration
    """

    def __init__(self, client: AppStoreConnectClient):
        """
        Initialize version operations.

        Args:
            client: App Store Connect client
        """
        self.client = client

    def create_version_interactive(
        self,
        app_id: str,
        version_string: str,
        platform: str = "IOS",
        auto_increment_on_conflict: bool = False,
    ) -> Tuple[VersionView, bool]:
        """
        Create version with smart conflict resolution.

        Args:
            app_id: App ID
            version_string: Desired version string
            platform: Platform
            auto_increment_on_conflict: Auto-increment patch version on conflict

        Returns:
            Tuple of (created_version, was_incremented)

        Raises:
            ValidationError: If version format invalid
            VersionConflictError: If conflict and auto_increment disabled
        """
        request = VersionCreationRequest(
            app_id=app_id, version_string=version_string, platform=platform
        )

        # Validate format
        if not request.validate_version_format():
            raise ValidationError(
                f"Invalid version format: {version_string}. Expected: MAJOR.MINOR[.PATCH]"
            )

        was_incremented = False

        # Try creating version
        result = self.client.create_version(request)

        match result:
            case ClientSuccess(data=created):
                return created, was_incremented
            case ClientError(error_message=err, error_code=code):
                # Check if it's a conflict error
                is_conflict = "conflict" in err.lower() or "already exists" in err.lower()

                if not is_conflict:
                    # Not a conflict error, raise generic exception
                    raise Exception(f"Failed to create version: {err}")

                # It's a conflict error
                if not auto_increment_on_conflict:
                    raise VersionConflictError(err)

                # Auto-increment patch version
                parts = version_string.split(".")
                if len(parts) == 2:
                    parts.append("1")  # Add patch if missing
                elif len(parts) >= 3:
                    parts[2] = str(int(parts[2]) + 1)  # Increment patch

                incremented_version = ".".join(parts[:3])

                # Retry with incremented version
                request.version_string = incremented_version
                retry_result = self.client.create_version(request)

                match retry_result:
                    case ClientSuccess(data=created):
                        was_incremented = True
                        return created, was_incremented
                    case ClientError(error_message=retry_err):
                        raise VersionConflictError(f"Failed even after incrementing: {retry_err}")

    def suggest_next_version(
        self, app_id: str, platform: str = "IOS", increment: str = "patch"
    ) -> str:
        """
        Suggest next version based on YY.WW.0 format (Year.Week.Patch).

        Format:
        - YY: 2-digit year (26 for 2026)
        - WW: ISO week number (1-53)
        - PATCH: Always 0 for new releases (hotfixes increment this)

        Args:
            app_id: App ID
            platform: Platform
            increment: Ignored (kept for compatibility)

        Returns:
            Suggested version string in YY.WW.0 format

        Example:
            If latest is 26.10.1, next is 26.11.0
            (next week, patch reset to 0)
        """
        # Get current date info
        now = datetime.now()
        current_year = now.year % 100  # Last 2 digits (26 for 2026)
        current_week = now.isocalendar()[1]  # ISO week number (1-53)

        # Get latest version (now returns ClientResult)
        latest_result = self.client.get_latest_version(app_id, platform=platform)

        # Use pattern matching to extract latest version
        latest = None
        match latest_result:
            case ClientSuccess(data=version):
                latest = version
            case ClientError():
                # If error getting versions, use current week
                return f"{current_year}.{current_week}.0"

        if not latest:
            # No versions exist, use current year and week
            return f"{current_year}.{current_week}.0"

        # Parse latest version
        parts = latest.version_string.split(".")
        if len(parts) < 2:
            # Invalid format, use current
            return f"{current_year}.{current_week}.0"

        try:
            latest_year = int(parts[0])
            latest_week = int(parts[1])
        except ValueError:
            # Non-numeric parts, use current
            return f"{current_year}.{current_week}.0"

        # Suggest next week of the same year, or current if we're ahead
        if current_year > latest_year:
            # New year, start with current week
            return f"{current_year}.{current_week}.0"
        elif current_year == latest_year:
            if current_week > latest_week:
                # Same year, we're in a later week
                return f"{current_year}.{current_week}.0"
            else:
                # Same or earlier week, suggest next week
                next_week = latest_week + 1
                if next_week > 53:
                    # Overflow to next year
                    return f"{current_year + 1}.1.0"
                return f"{current_year}.{next_week}.0"
        else:
            # We're behind the latest year somehow, suggest current
            return f"{current_year}.{current_week}.0"

    def compare_versions(
        self, version1: str, version2: str
    ) -> int:
        """
        Compare two version strings.

        Args:
            version1: First version
            version2: Second version

        Returns:
            -1 if version1 < version2
             0 if version1 == version2
             1 if version1 > version2
        """
        def parse_version(v: str) -> List[int]:
            parts = v.split(".")
            return [int(p) for p in parts]

        v1_parts = parse_version(version1)
        v2_parts = parse_version(version2)

        # Pad to same length
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))

        for p1, p2 in zip(v1_parts, v2_parts):
            if p1 < p2:
                return -1
            elif p1 > p2:
                return 1

        return 0

    def get_versions_summary_table(
        self, app_id: str, platform: str = "IOS", limit: int = 10
    ) -> List[str]:
        """
        Get formatted table of versions.

        Args:
            app_id: App ID
            platform: Platform
            limit: Max versions to return

        Returns:
            List of formatted lines for display
        """
        versions_result = self.client.list_versions(app_id, platform=platform, as_summary=True)

        # Handle ClientResult
        match versions_result:
            case ClientSuccess(data=versions):
                # Sort by version (newest first)
                sorted_versions = sorted(
                    versions,
                    key=lambda v: [int(p) for p in v.version_string.split(".")],
                    reverse=True,
                )
            case ClientError():
                # If error, return empty list
                sorted_versions = []

        # Limit results
        sorted_versions = sorted_versions[:limit]

        # Format as table
        lines = []
        lines.append("Existing Versions:")
        lines.append("-" * 60)

        for version in sorted_versions:
            lines.append(version.display_line())

        if not sorted_versions:
            lines.append("(No versions found)")

        return lines

    def validate_version_creation(
        self, app_id: str, version_string: str, platform: str = "IOS"
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if version can be created.

        Args:
            app_id: App ID
            version_string: Version to validate
            platform: Platform

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check format
        parts = version_string.split(".")
        if len(parts) < 2 or len(parts) > 4:
            return False, "Version must have 2-4 parts (e.g., 1.2.3)"

        if not all(p.isdigit() for p in parts):
            return False, "Version parts must be numeric"

        # Check for conflict
        exists_result = self.client.version_exists(app_id, version_string, platform)

        match exists_result:
            case ClientSuccess(data=exists):
                if exists:
                    return False, f"Version {version_string} already exists"
            case ClientError(error_message=err):
                # If we can't check, assume it doesn't exist (let create_version handle it)
                pass

        return True, None
