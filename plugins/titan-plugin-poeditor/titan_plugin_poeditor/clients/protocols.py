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

    def get_project_languages(self, project_id: str) -> ClientResult[list[str]]:
        """Get all language codes for a project."""
        ...

    def add_terms(self, project_id: str, terms: list[dict]) -> ClientResult[dict]:
        """Add new terms to a project."""
        ...

    def create_terms_with_translations(
        self,
        project_id: str,
        terms_map: dict[str, str],
        translations_by_language: dict[str, dict[str, str]],
        source_language: str
    ) -> ClientResult[dict]:
        """Create terms in PoEditor and add translations for all languages."""
        ...
