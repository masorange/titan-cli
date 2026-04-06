"""
Build Operations - Business logic for build and submission workflows.

These operations contain no API calls - they are pure business logic
for data transformation, validation, and workflow coordination.
"""

from typing import Dict, List, Tuple, Optional
from ..models.view import AppView, BuildView, WhatsNewPreview


# Standard What's New texts (Phase 1)
WHATS_NEW_TEXT_ES = "Corrección de errores menores y mejoras de rendimiento"
WHATS_NEW_TEXT_EN = "Minor bug fixing and improvements"


def prepare_whats_new_previews(selected_apps: List[AppView]) -> List[WhatsNewPreview]:
    """
    Prepare What's New preview data for selected apps.

    Args:
        selected_apps: List of selected app models

    Returns:
        List of WhatsNewPreview models for display
    """
    previews = []

    for app in selected_apps:
        preview = WhatsNewPreview(
            brand_name=app.get_brand(),
            app_id=app.id,
            text_es=WHATS_NEW_TEXT_ES,
            text_en=WHATS_NEW_TEXT_EN,
        )
        previews.append(preview)

    return previews


def get_whats_new_texts() -> Dict[str, str]:
    """
    Get standard What's New texts for both locales.

    Returns:
        Dictionary with locale codes as keys and texts as values
    """
    return {
        "es-ES": WHATS_NEW_TEXT_ES,
        "en-US": WHATS_NEW_TEXT_EN,
    }


def format_build_for_selection(build: BuildView) -> Tuple[str, str, str]:
    """
    Format build data for selection display.

    Args:
        build: Build view model

    Returns:
        Tuple of (value, title, description) for selection widget
    """
    value = build.id
    title = f"Build {build.version}"

    # Format upload date
    upload_info = ""
    if build.uploaded_date:
        try:
            from datetime import datetime

            dt = datetime.fromisoformat(build.uploaded_date.replace("Z", "+00:00"))
            upload_info = f"Uploaded: {dt.strftime('%Y-%m-%d %H:%M')}"
        except:
            upload_info = f"Uploaded: {build.uploaded_date}"

    # Format status
    status = build.processing_state or "VALID"
    if build.expired:
        status = "EXPIRED"

    status_emoji = {
        "VALID": "✅",
        "PROCESSING": "🔄",
        "INVALID": "❌",
        "EXPIRED": "⏰",
    }
    emoji = status_emoji.get(status, "❓")

    description = f"{emoji} {upload_info} · Status: {status}"

    return (value, title, description)


def filter_valid_builds(builds: List[BuildView]) -> List[BuildView]:
    """
    Filter builds to only include valid, non-expired ones.

    Args:
        builds: List of build view models

    Returns:
        Filtered list of valid builds
    """
    return [
        build
        for build in builds
        if not build.expired and build.processing_state in ("VALID", None)
    ]


def group_builds_by_brand(
    apps: List[AppView], all_builds: Dict[str, List[BuildView]]
) -> Dict[str, Tuple[AppView, List[BuildView]]]:
    """
    Group builds by brand for organized display.

    Args:
        apps: List of app view models
        all_builds: Dictionary mapping app_id to list of builds

    Returns:
        Dictionary mapping brand name to (app, builds) tuple
    """
    grouped = {}

    for app in apps:
        brand = app.get_brand()
        builds = all_builds.get(app.id, [])

        if brand not in grouped:
            grouped[brand] = []

        grouped[brand].append((app, builds))

    return grouped


def create_submission_summary(
    selected_builds: Dict[str, str], apps: List[AppView]
) -> List[Tuple[str, str, str]]:
    """
    Create a summary of what will be submitted.

    Args:
        selected_builds: Dictionary mapping app_id to build_id
        apps: List of app view models

    Returns:
        List of (brand_name, app_name, build_id) tuples for display
    """
    summary = []

    for app in apps:
        if app.id in selected_builds:
            brand = app.get_brand()
            build_id = selected_builds[app.id]

            summary.append((brand, app.name, build_id))

    return summary


def validate_submission_readiness(
    app_id: str, build_id: str, whats_new_locales: List[str]
) -> Tuple[bool, List[str]]:
    """
    Validate that a version is ready for submission.

    Args:
        app_id: App ID
        build_id: Build ID
        whats_new_locales: List of locale codes with What's New text

    Returns:
        Tuple of (is_ready, list_of_errors)
    """
    errors = []

    if not build_id:
        errors.append("No build assigned")

    required_locales = {"es-ES", "en-US"}
    missing_locales = required_locales - set(whats_new_locales)
    if missing_locales:
        errors.append(f"Missing What's New for locales: {', '.join(missing_locales)}")

    is_ready = len(errors) == 0

    return (is_ready, errors)


def find_common_build_numbers(
    builds_by_app: Dict[str, List[BuildView]]
) -> List[str]:
    """
    Find build numbers that are available across ALL apps.

    Note: This finds common build NUMBERS (e.g., "3478"), not build IDs.
    Each app will have its own build with that number (different build_id).

    Args:
        builds_by_app: Dictionary mapping app_id to list of builds

    Returns:
        List of build numbers available in all apps (sorted newest first)
    """
    if not builds_by_app:
        return []

    # Get build numbers from first app
    first_app_builds = next(iter(builds_by_app.values()))
    common_numbers = set(b.version for b in first_app_builds)

    # Intersect with build numbers from other apps
    for builds in builds_by_app.values():
        app_numbers = set(b.version for b in builds)
        common_numbers &= app_numbers

    # Sort by numeric value (descending - newest first)
    try:
        return sorted(common_numbers, key=int, reverse=True)
    except ValueError:
        # If not all numeric, sort as strings
        return sorted(common_numbers, reverse=True)


def find_build_by_number(builds: List[BuildView], build_number: str) -> Optional[BuildView]:
    """
    Find a build by its build number (version field).

    Args:
        builds: List of builds to search
        build_number: Build number to find (e.g., "3478")

    Returns:
        BuildView if found, None otherwise
    """
    for build in builds:
        if build.version == build_number:
            return build
    return None
