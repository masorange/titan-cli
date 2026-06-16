"""Protocol definitions for PoEditor client."""

from typing import Protocol

from titan_cli.core.result import ClientResult

from ..models import UIPoEditorProject
from ..models.view import TermsWithTranslationsResult


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

    def create_terms_with_translations(
        self,
        project_id: str,
        terms_map: dict[str, str],
        translations_by_language: dict[str, dict[str, str]],
        source_language: str
    ) -> ClientResult[TermsWithTranslationsResult]:
        """Create terms in PoEditor and add translations for all languages."""
        ...

    def delete_term(self, project_id: str, term_key: str) -> ClientResult[dict]:
        """Delete a term from a PoEditor project."""
        ...
