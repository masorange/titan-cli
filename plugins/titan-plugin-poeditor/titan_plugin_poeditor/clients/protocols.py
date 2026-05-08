"""Protocol definitions for PoEditor client."""

from typing import Protocol

from titan_cli.core.result import ClientResult

from ..models import UIPoEditorProject


class PoEditorClientProtocol(Protocol):
    """Protocol for PoEditor client interface.

    Defines the public API that all PoEditor clients must implement.
    Useful for testing and dependency injection.
    """

    def list_projects(self) -> ClientResult[list[UIPoEditorProject]]:
        """List all projects accessible to the user."""
        ...

    def get_project(self, project_id: str) -> ClientResult[UIPoEditorProject]:
        """Get project by ID."""
        ...

    def upload_file(
        self, project_id: str, file_path: str, language_code: str
    ) -> ClientResult[dict]:
        """Upload translation file to project."""
        ...
