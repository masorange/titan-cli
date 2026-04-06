"""
View models - Simplified models optimized for TUI display.

These models contain only the data needed for user interactions
and are designed for easy rendering in terminal UI.
"""

from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


class AppView(BaseModel):
    """
    Simplified app model for TUI.

    Contains only essential fields for app selection and display.
    """
    id: str
    name: str
    bundle_id: str
    sku: str
    primary_locale: str

    def display_name(self) -> str:
        """Format for dropdown/selection display."""
        return f"{self.name} ({self.bundle_id})"

    def get_brand(self) -> str:
        """
        Extract brand name from app name or bundle ID.

        Returns:
            Brand name (e.g., "Yoigo", "Jazztel", "Guuk", "Lebara", etc.)
        """
        # Try to extract from name first
        name_lower = self.name.lower()

        # Common brand patterns (9 brands in MasOrange account)
        if "yoigo" in name_lower:
            return "Yoigo"
        elif "jazztel" in name_lower:
            return "Jazztel"
        elif "guuk" in name_lower:
            return "Guuk"
        elif "lebara" in name_lower:
            return "Lebara"
        elif "llamaya" in name_lower:
            return "Llamaya"
        elif "lyca" in name_lower:
            return "Lyca"
        elif "sweno" in name_lower:
            return "Sweno"
        elif "másmóvil" in name_lower or "masmovil" in name_lower:
            return "MÁSMÓVIL"
        elif "freyja" in name_lower or "orange" in name_lower or "masorange" in name_lower:
            return "Orange"

        # Fallback to bundle ID
        bundle_lower = self.bundle_id.lower()
        if "yoigo" in bundle_lower:
            return "Yoigo"
        elif "jazztel" in bundle_lower:
            return "Jazztel"
        elif "guuk" in bundle_lower:
            return "Guuk"
        elif "lebara" in bundle_lower:
            return "Lebara"
        elif "llamaya" in bundle_lower:
            return "Llamaya"
        elif "lyca" in bundle_lower:
            return "Lyca"
        elif "sweno" in bundle_lower:
            return "Sweno"
        elif "masmovil" in bundle_lower:
            return "MÁSMÓVIL"
        elif "orange" in bundle_lower:
            return "Orange"

        # Default: use app name
        return self.name

    def __str__(self) -> str:
        return self.display_name()


class VersionView(BaseModel):
    """
    Full version model for TUI with formatted display fields.

    Used when showing detailed version information.
    """
    id: str
    version_string: str
    platform: str
    state: Optional[str] = None
    release_type: Optional[str] = None
    copyright: Optional[str] = None
    earliest_release_date: Optional[str] = None
    created_date: Optional[str] = None
    downloadable: bool = False

    # Computed display fields
    state_display: str = "Unknown"
    release_type_display: str = "Manual"
    platform_display: str = "iOS"

    def format_state(self) -> str:
        """
        Format state for display with emoji indicators.

        Returns:
            Formatted state string (e.g., "🟢 Ready for Sale")
        """
        state_map = {
            "READY_FOR_SALE": "🟢 Ready for Sale",
            "PROCESSING_FOR_APP_STORE": "🟡 Processing",
            "PENDING_DEVELOPER_RELEASE": "🟠 Pending Release",
            "PREPARE_FOR_SUBMISSION": "⚪ Prepare for Submission",
            "WAITING_FOR_REVIEW": "🔵 Waiting for Review",
            "IN_REVIEW": "🔵 In Review",
            "REJECTED": "🔴 Rejected",
            "DEVELOPER_REMOVED_FROM_SALE": "⚫ Removed from Sale",
            "DEVELOPER_REJECTED": "🔴 Developer Rejected",
        }
        return state_map.get(self.state or "", f"❓ {self.state or 'Unknown'}")

    def format_platform(self) -> str:
        """Format platform for display."""
        platform_map = {
            "IOS": "iOS",
            "MAC_OS": "macOS",
            "TV_OS": "tvOS",
            "VISION_OS": "visionOS",
        }
        return platform_map.get(self.platform, self.platform)

    def format_release_type(self) -> str:
        """Format release type for display."""
        release_map = {
            "MANUAL": "Manual Release",
            "AFTER_APPROVAL": "Auto Release After Approval",
            "SCHEDULED": "Scheduled Release",
        }
        return release_map.get(self.release_type or "", "Manual Release")

    def __str__(self) -> str:
        """String representation for display."""
        return f"{self.version_string} - {self.format_state()}"


class VersionSummaryView(BaseModel):
    """
    Minimal version model for lists/tables.

    Used when showing multiple versions in a list or table.
    """
    id: str
    version_string: str
    state: Optional[str] = None
    platform: str = "IOS"
    created_date: Optional[str] = None

    def display_line(self) -> str:
        """
        Format as single line for table/list display.

        Returns:
            Compact single-line representation
        """
        state_emoji = {
            "READY_FOR_SALE": "🟢",
            "PREPARE_FOR_SUBMISSION": "⚪",
            "WAITING_FOR_REVIEW": "🔵",
            "IN_REVIEW": "🔵",
            "REJECTED": "🔴",
        }
        emoji = state_emoji.get(self.state or "", "❓")

        created = ""
        if self.created_date:
            try:
                dt = datetime.fromisoformat(self.created_date.replace("Z", "+00:00"))
                created = f" (created {dt.strftime('%Y-%m-%d')})"
            except:
                pass

        return f"{emoji} {self.version_string:<8} {self.state or 'Unknown':<25}{created}"

    def __str__(self) -> str:
        return f"{self.version_string} ({self.state or 'Unknown'})"


class VersionCreationRequest(BaseModel):
    """
    Request model for creating a new version.

    Used to collect and validate user input before API call.
    """
    app_id: str
    version_string: str
    platform: str = "IOS"
    release_type: str = "MANUAL"
    copyright: Optional[str] = None
    earliest_release_date: Optional[str] = None

    def validate_version_format(self) -> bool:
        """
        Validate version string format.

        Returns:
            True if version format is valid (e.g., "1.2.3")
        """
        parts = self.version_string.split(".")
        if len(parts) < 2 or len(parts) > 4:
            return False
        return all(part.isdigit() for part in parts)


class BuildView(BaseModel):
    """
    Build model for TUI display.

    Represents a build uploaded via Xcode or CI/CD.
    """
    id: str
    version: str  # Build version (e.g., "1.2.3")
    uploaded_date: Optional[str] = None
    processing_state: Optional[str] = None
    expired: bool = False

    def display_line(self) -> str:
        """
        Format as single line for selection display.

        Returns:
            Compact single-line representation
        """
        state_emoji = {
            "VALID": "✅",
            "PROCESSING": "🔄",
            "INVALID": "❌",
            "EXPIRED": "⏰",
        }
        emoji = state_emoji.get(self.processing_state or "VALID", "❓")

        upload_date = ""
        if self.uploaded_date:
            try:
                dt = datetime.fromisoformat(self.uploaded_date.replace("Z", "+00:00"))
                upload_date = f"Uploaded: {dt.strftime('%Y-%m-%d %H:%M')}"
            except:
                upload_date = f"Uploaded: {self.uploaded_date}"

        status = self.processing_state or "VALID"
        if self.expired:
            status = "EXPIRED"

        return f"{emoji} Build {self.version:<10} {upload_date:<30} {status}"

    def __str__(self) -> str:
        return f"Build {self.version} ({self.processing_state or 'VALID'})"


class WhatsNewPreview(BaseModel):
    """
    Preview model for What's New text per brand.

    Used to show preview before submission.
    """
    brand_name: str
    app_id: str
    text_es: str
    text_en: str

    def format_table_row(self) -> tuple:
        """
        Format as table row (brand, ES text, EN text).

        Returns:
            Tuple of (brand, text_es, text_en)
        """
        return (self.brand_name, self.text_es, self.text_en)


class AppSubmissionPackage(BaseModel):
    """
    Complete package for an app version submission.

    Contains all information needed to submit an app version for review,
    including app details, version info, build assignment, and submission state.

    This model is used throughout the submission workflow to track the complete
    state of each app's submission and avoid confusion between build_id (unique
    per app) and build_number (can be the same across apps).
    """
    # App identification
    app_id: str
    app_name: str
    brand: str

    # Version information
    version_id: str
    version_string: str
    version_state: str

    # Build assignment
    build_id: Optional[str] = None
    build_number: Optional[str] = None  # e.g., "3478" - can match across apps
    build_uploaded_date: Optional[str] = None

    # Release notes (localizations)
    whats_new_es: str = ""
    whats_new_en: str = ""

    # Submission readiness
    is_ready_to_submit: bool = False
    readiness_errors: List[str] = []
    is_already_submitted: bool = False

    # Display fields (set by report generator)
    status_emoji: str = ""
    status_text: str = ""
    error: Optional[str] = None

    def assign_build(self, build: BuildView) -> None:
        """
        Assign a build to this submission package.

        Args:
            build: BuildView model to assign
        """
        self.build_id = build.id
        self.build_number = build.version
        self.build_uploaded_date = build.uploaded_date
        self._check_readiness()

    def set_whats_new(self, text_es: str, text_en: str) -> None:
        """
        Set What's New text for both locales.

        Args:
            text_es: Spanish text
            text_en: English text
        """
        self.whats_new_es = text_es
        self.whats_new_en = text_en
        self._check_readiness()

    def _check_readiness(self) -> None:
        """
        Check if package is ready for submission and update state.

        Updates is_ready_to_submit and readiness_errors based on current state.
        """
        errors = []

        if not self.build_id:
            errors.append("No build assigned")

        if not self.whats_new_es:
            errors.append("Missing Spanish What's New text")

        if not self.whats_new_en:
            errors.append("Missing English What's New text")

        if self.version_state in ("WAITING_FOR_REVIEW", "IN_REVIEW", "READY_FOR_SALE"):
            errors.append(f"Version already in state: {self.version_state}")
            self.is_already_submitted = True

        self.readiness_errors = errors
        self.is_ready_to_submit = len(errors) == 0 and not self.is_already_submitted

    def get_summary(self) -> str:
        """
        Get a summary string for display.

        Returns:
            Human-readable summary of package state
        """
        status_emoji = "✅" if self.is_ready_to_submit else "❌"
        build_info = f"build {self.build_number}" if self.build_number else "no build"
        return f"{status_emoji} {self.brand}: v{self.version_string} ({build_info})"
