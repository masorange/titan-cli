"""Pure business logic operations for projects.

Operations are pure functions with no side effects.
They can use the client for API calls but should not depend on UI.
"""

from titan_cli.core.result import ClientError, ClientSuccess

from ..clients import PoEditorClient
from ..models import UIPoEditorProject


def find_project_by_name(
    poeditor_client: PoEditorClient, name: str, projects: list | None = None
) -> UIPoEditorProject | None:
    """Find a project by name (case-insensitive).

    Pure business logic - no API calls if projects provided.

    Args:
        poeditor_client: PoEditor client (only for API if needed)
        name: Project name to search for
        projects: Optional pre-fetched project list

    Returns:
        UIPoEditorProject if found, None otherwise

    Raises:
        Exception: If lookup fails
    """
    # Use provided list if available (avoid API call)
    if projects:
        matching = [p for p in projects if p.name.lower() == name.lower()]
        return matching[0] if matching else None

    # Otherwise fetch from API
    result = poeditor_client.list_projects()

    match result:
        case ClientSuccess(data=all_projects):
            matching = [p for p in all_projects if p.name.lower() == name.lower()]
            return matching[0] if matching else None
        case ClientError(error_message=err):
            raise Exception(f"Failed to find project: {err}")


def calculate_overall_progress(projects: list[UIPoEditorProject]) -> float:
    """Calculate average translation progress across all projects.

    Pure function - no side effects, no API calls.

    Args:
        projects: List of UIPoEditorProject

    Returns:
        Average completion percentage (0-100)
    """
    if not projects:
        return 0.0

    # Progress is indicated by the icon mapping:
    # 🟢 = 100%, 🟡 = 75%, 🟠 = 25%, 🔴 = 0%
    icon_to_percentage = {"🟢": 100.0, "🟡": 75.0, "🟠": 25.0, "🔴": 0.0}

    total_progress = sum(
        icon_to_percentage.get(p.progress_icon, 0.0) for p in projects
    )

    return total_progress / len(projects) if projects else 0.0
