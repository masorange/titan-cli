"""PoEditor Client Facade - Public API."""

from titan_cli.core.result import ClientResult

from ..models import UIPoEditorProject
from ..models.view import TermsAddResult
from .network import PoEditorNetwork
from .services import ProjectService, TermService, UploadService


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
        self._upload_service = UploadService(self._network)

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

    def upload_file(
        self,
        project_id: str,
        file_path: str,
        language_code: str,
        updating: str = "terms_translations",
    ) -> ClientResult[dict]:
        """Upload translation file to project.

        Args:
            project_id: PoEditor project ID
            file_path: Path to translation file
            language_code: Language code (e.g., "en", "es", "fr")
            updating: What to update - "terms", "terms_translations", or "translations"

        Returns:
            ClientResult[dict] with upload statistics
        """
        return self._upload_service.upload_file(
            project_id, file_path, language_code, updating
        )

    def get_project_languages(self, project_id: str) -> ClientResult[list[str]]:
        """Get all language codes for a project.

        Args:
            project_id: PoEditor project ID

        Returns:
            ClientResult with list of language codes or error
        """
        return self._term_service.get_project_languages(project_id)

    def add_terms(self, project_id: str, terms: list[dict]) -> ClientResult[TermsAddResult]:
        """Add new terms to a project.

        Adds terms to a localization project following POEditor API v2 spec:
        https://poeditor.com/docs/api#terms_add

        Args:
            project_id: PoEditor project ID
            terms: List of term objects. Each can contain:
                - term (str): The text string - REQUIRED
                - context (str, optional): Contextual information
                - reference (str, optional): Location reference
                - plural (str, optional): Plural form
                - comment (str, optional): Translator notes
                - tags (list|str, optional): Tag names

        Returns:
            ClientResult[TermsAddResult] with statistics:
                - parsed (int): Number of terms parsed
                - added (int): Number of terms added

        Example:
            >>> result = client.add_terms(
            ...     project_id="7717",
            ...     terms=[{"term": "Add new list"}]
            ... )
        """
        return self._term_service.add_terms(project_id, terms)

    def create_terms_with_translations(
        self,
        project_id: str,
        terms_map: dict[str, str],
        translations_by_language: dict[str, dict[str, str]],
        source_language: str = "en"
    ) -> ClientResult[dict]:
        """Create terms in PoEditor and add translations for all languages.

        Args:
            project_id: PoEditor project ID
            terms_map: Dict mapping term keys to source language values
            translations_by_language: Dict mapping language codes to term translations
            source_language: Source language code for terms_map values (default: "en")

        Returns:
            ClientResult with success statistics or error
        """
        return self._term_service.create_terms_with_translations(
            project_id,
            terms_map,
            translations_by_language,
            source_language
        )
