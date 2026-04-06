"""
Brand Detector - Automatically detect brands from the Brands/ directory.
"""

from pathlib import Path
from typing import List, Set


def get_project_brands() -> List[str]:
    """
    Detect brands from the Brands/ directory in the project.

    Returns:
        List of brand names (lowercase) found in Brands/
        Returns empty list if Brands/ directory not found
    """
    # Try to find Brands directory
    current_dir = Path.cwd()
    brands_dir = None

    # Search up to 3 levels up for Brands directory
    for parent in [current_dir] + list(current_dir.parents)[:3]:
        potential_brands = parent / "Brands"
        if potential_brands.exists() and potential_brands.is_dir():
            brands_dir = potential_brands
            break

    if not brands_dir:
        return []

    # Get all subdirectories in Brands/ (each is a brand)
    brands = []
    try:
        for item in brands_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                brands.append(item.name.lower())
    except Exception:
        return []

    return sorted(brands)


def get_brand_bundle_patterns() -> Set[str]:
    """
    Get bundle ID patterns for known brands.

    This maps brand directory names to their bundle ID patterns.
    Helps filter App Store Connect apps by bundle ID.

    Returns:
        Set of bundle ID patterns (lowercase)
    """
    brands = get_project_brands()

    # Known bundle ID patterns for each brand
    # Format: brand_dir_name -> bundle_id_pattern
    bundle_patterns = {
        "yoigo": ["miyoigo", "yoigo"],
        "jazztel": ["jazztel"],
        "euskaltel": ["euskaltel", "moveus"],
        "guuk": ["guuk", "miguuk"],
        "lebara": ["lebara", "milebara"],
        "llamaya": ["llamaya", "millamaya"],
        "lycamobile": ["lycamobile", "milycamobile"],
        "masmovil": ["masmovil", "mimasmovil"],
        "mundor": ["mundor"],
        "sweno": ["sweno", "misweno"],
        "telecable": ["telecable"],
    }

    # Build set of patterns for detected brands
    patterns = set()
    for brand in brands:
        if brand in bundle_patterns:
            patterns.update(bundle_patterns[brand])

    return patterns


def filter_apps_by_brands(apps: List[any]) -> List[any]:
    """
    Filter apps list to only include those matching project brands.

    Args:
        apps: List of app objects with 'name' and 'bundle_id' attributes

    Returns:
        Filtered list of apps matching project brands
        Returns all apps if no brands detected
    """
    patterns = get_brand_bundle_patterns()

    if not patterns:
        # No brands detected, return all apps
        return apps

    # Keywords to exclude (non-main apps and services)
    exclude_keywords = [
        # Media & Entertainment
        "tv", "television",
        # Professional Services
        "asesor", "abogado", "lawyer",
        # Security & Alarms
        "alarm", "alarma", "segur",
        # Health Services
        "doctor", "medic", "salud", "teleasistencia", "reloj",
        # Energy & Utilities
        "luz", "gas", "energia", "energy",
        # Banking & Finance
        "banco", "bank", "telebanco",
        # Other Services
        "usuario", "servicios r",
    ]

    # Filter apps by bundle ID patterns
    filtered = []
    for app in apps:
        app_name_lower = app.name.lower()
        bundle_id_lower = app.bundle_id.lower()

        # Check if app matches any brand pattern
        # Only match MAIN apps (exclude services, TV, etc.)
        is_excluded = any(
            keyword in app_name_lower or keyword in bundle_id_lower
            for keyword in exclude_keywords
        )

        # Special case: check for "TB" suffix (TeleBanco)
        if app.name.endswith(" TB") or "tb" in bundle_id_lower:
            is_excluded = True

        if not is_excluded:
            # Check if matches any brand pattern
            matches = any(
                pattern in app_name_lower or pattern in bundle_id_lower
                for pattern in patterns
            )
            if matches:
                filtered.append(app)

    return filtered if filtered else apps  # Fallback to all if no matches


__all__ = [
    "get_project_brands",
    "get_brand_bundle_patterns",
    "filter_apps_by_brands",
]
