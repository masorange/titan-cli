"""Pure mappers: Firebase Management project payloads to UI models."""

from __future__ import annotations

from ..network.rest import NetworkFirebaseProject
from ..view import UIFirebaseProject


def map_project(project: NetworkFirebaseProject) -> UIFirebaseProject:
    """Map one FirebaseProject network model to its UI model."""
    return UIFirebaseProject(
        project_id=project.project_id,
        display_name=project.display_name,
        name=project.name,
        project_number=project.project_number,
    )
