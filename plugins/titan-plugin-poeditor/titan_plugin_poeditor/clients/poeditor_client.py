"""PoEditor Client Facade - Public API."""

from titan_cli.core.result import ClientResult

from ..models import UIPoEditorProject
from ..models.view import TermsWithTranslationsResult
from .network import PoEditorNetwork
from .services import ProjectService, TermService


class PoEditorClient:
    """PoEditor Client Facade.

    Public API for the PoEditor plugin.
    Delegates all work to internal services.

    All methods return ClientResult[T] for type-safe error handling.
    Use pattern matching to handle success and error cases.

    Example:
        >>> client = PoEditorClient(api_token="...")
        >>> result = client.list_projects()
        >>> match result:
        ...     case ClientSuccess(data=projects):
        ...         for p in projects:
        ...             print(p.name)
        ...     case ClientError(error_message=err):
        ...         print(f"Error: {err}")
    """

    def __init__(self, api_token: str, timeout: int = 30):
        """Initialize PoEditor client.

        Args:
            api_token: PoEditor API token
            timeout: Request timeout in seconds
        """
        # Internal dependencies (private)
        self._network = PoEditorNetwork(api_token, timeout)
        self._project_service = ProjectService(self._network)
        self._term_service = TermService(self._network)

    def list_projects(self) -> ClientResult[list[UIPoEditorProject]]:
        """List all projects accessible to the user.

        Returns:
            ClientResult[List[UIPoEditorProject]]
        """
        return self._project_service.list_projects()

    def get_project(self, project_id: str) -> ClientResult[UIPoEditorProject]:
        """Get project by ID with languages.

        Args:
            project_id: PoEditor project ID

        Returns:
            ClientResult[UIPoEditorProject]
        """
        return self._project_service.get_project(project_id)

    def create_terms_with_translations(
        self,
        project_id: str,
        terms_map: dict[str, str],
        translations_by_language: dict[str, dict[str, str]],
        source_language: str = "en"
    ) -> ClientResult[TermsWithTranslationsResult]:
        """Create terms in PoEditor and add translations for all languages.

        Args:
            project_id: PoEditor project ID
            terms_map: Dict mapping term keys to source language values
                      Example: {"home_title": "Home", "settings_title": "Settings"}
            translations_by_language: Dict mapping language codes to term translations
                      Example: {"es": {"home_title": "Inicio"}, "fr": {"home_title": "Accueil"}}
            source_language: Source language code for terms_map values (default: "en")

        Returns:
            ClientResult[TermsWithTranslationsResult] with success statistics or error
        """
        return self._term_service.create_terms_with_translations(
            project_id,
            terms_map,
            translations_by_language,
            source_language
        )

    def delete_term(self, project_id: str, term_key: str) -> ClientResult[dict]:
        """Delete a term from a PoEditor project.

        Args:
            project_id: PoEditor project ID
            term_key: The term key to delete

        Returns:
            ClientResult with deletion info or error

        Example:
            >>> result = client.delete_term(
            ...     project_id="123456",
            ...     term_key="home_title"
            ... )
        """
        return self._term_service.delete_term(project_id, term_key)
