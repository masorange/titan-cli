"""Service for PoEditor term and translation operations."""

from titan_cli.core.logging import log_client_operation
from titan_cli.core.result import ClientError, ClientResult, ClientSuccess

from ...exceptions import PoEditorAPIError
from ...models.view import TermsWithTranslationsResult
from ..network import PoEditorNetwork


class TermService:
    """Service for PoEditor term and translation operations.

    PRIVATE - only used by PoEditorClient.
    Handles: add/update terms, add/update translations.
    """

    def __init__(self, network: PoEditorNetwork):
        """Initialize service with network layer.

        Args:
            network: PoEditorNetwork instance
        """
        self.network = network

    @log_client_operation()
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
            ClientResult with success statistics or error
        """
        try:
            # First, add the terms to the project
            terms_payload = [
                {"term": term_key}
                for term_key in terms_map.keys()
            ]

            add_terms_result = self._add_terms(project_id, terms_payload)

            if isinstance(add_terms_result, ClientError):
                return ClientError(
                    error_message=f"Failed to add terms: {add_terms_result.error_message}",
                    error_code=add_terms_result.error_code
                )

            # Add source language translations from terms_map
            source_translations_payload = [
                {
                    "term": term_key,
                    "translation": {
                        "content": term_value
                    }
                }
                for term_key, term_value in terms_map.items()
            ]

            source_result = self._add_translations(project_id, source_language, source_translations_payload)
            failed_languages = []

            if isinstance(source_result, ClientError):
                failed_languages.append(f"{source_language} (source): {source_result.error_message}")

            # Then add translations for each language
            for language_code, translations in translations_by_language.items():
                # Skip source language if already in translations_by_language
                if language_code == source_language:
                    continue

                translations_payload = [
                    {
                        "term": term_key,
                        "translation": {
                            "content": translation_value
                        }
                    }
                    for term_key, translation_value in translations.items()
                ]

                result = self._add_translations(project_id, language_code, translations_payload)

                if isinstance(result, ClientError):
                    failed_languages.append(f"{language_code}: {result.error_message}")

            if failed_languages:
                return ClientError(
                    error_message=f"Terms added but some translations failed:\n" +
                    "\n".join(f"  - {err}" for err in failed_languages),
                    error_code="PARTIAL_FAILURE"
                )

            return ClientSuccess(
                data=TermsWithTranslationsResult(
                    terms_added=len(terms_map),
                    languages_updated=len(translations_by_language)
                ),
                message=f"Added {len(terms_map)} terms and updated {len(translations_by_language)} languages"
            )

        except PoEditorAPIError as e:
            return ClientError(
                error_message=f"Failed to create terms with translations: {e.message}",
                error_code="API_ERROR",
                details={"status_code": e.status_code},
            )
        except Exception as e:
            return ClientError(
                error_message=f"Unexpected error creating terms with translations: {e}",
                error_code="INTERNAL_ERROR",
            )

    @log_client_operation()
    def delete_term(self, project_id: str, term_key: str) -> ClientResult[dict]:
        """Delete a term from a PoEditor project.

        Args:
            project_id: PoEditor project ID
            term_key: The term key to delete

        Returns:
            ClientResult with deletion info or error
        """
        try:
            import json

            if not term_key or not term_key.strip():
                return ClientError(
                    error_message="term_key cannot be empty",
                    error_code="INVALID_PARAMETER"
                )

            # PoEditor API expects a list of terms to delete
            terms_payload = [{"term": term_key}]

            data = self.network.make_request(
                "terms/delete",
                id=project_id,
                data=json.dumps(terms_payload)
            )

            # Extract deletion statistics
            terms_result = data.get("terms", {})
            deleted = terms_result.get("deleted", 0)

            if deleted == 0:
                return ClientError(
                    error_message=f"Term '{term_key}' not found in project",
                    error_code="TERM_NOT_FOUND"
                )

            return ClientSuccess(
                data={"deleted": deleted, "term_key": term_key},
                message=f"Successfully deleted term '{term_key}'"
            )

        except PoEditorAPIError as e:
            return ClientError(
                error_message=f"Failed to delete term: {e.message}",
                error_code="API_ERROR",
                details={"status_code": e.status_code},
            )
        except Exception as e:
            return ClientError(
                error_message=f"Unexpected error deleting term: {e}",
                error_code="INTERNAL_ERROR",
            )

    def _add_terms(self, project_id: str, terms: list[dict]) -> ClientResult[dict]:
        """Add terms to project (PRIVATE).

        Args:
            project_id: PoEditor project ID
            terms: List of term dicts with "term" key

        Returns:
            ClientResult with add statistics or error
        """
        try:
            import json

            if not terms:
                return ClientError(
                    error_message="terms list cannot be empty",
                    error_code="INVALID_PARAMETER"
                )

            data = self.network.make_request(
                "terms/add",
                id=project_id,
                data=json.dumps(terms)
            )

            terms_result = data.get("terms", {})
            parsed = terms_result.get("parsed", 0)
            added = terms_result.get("added", 0)

            return ClientSuccess(
                data={"parsed": parsed, "added": added},
                message=f"Parsed {parsed} terms, added {added}"
            )

        except PoEditorAPIError as e:
            return ClientError(
                error_message=f"Failed to add terms: {e.message}",
                error_code="API_ERROR",
                details={"status_code": e.status_code},
            )
        except Exception as e:
            return ClientError(
                error_message=f"Unexpected error adding terms: {e}",
                error_code="INTERNAL_ERROR",
            )

    def _add_translations(
        self,
        project_id: str,
        language: str,
        translations: list[dict]
    ) -> ClientResult[dict]:
        """Add/update translations for a specific language (PRIVATE).

        Args:
            project_id: PoEditor project ID
            language: Language code (e.g., "en", "es", "fr")
            translations: List of dicts with "term" and "translation"
                         Example: [{"term": "home_title", "translation": {"content": "Home"}}]

        Returns:
            ClientResult with translation update info or error
        """
        try:
            import json
            data = self.network.make_request(
                "translations/update",
                id=project_id,
                language=language,
                data=json.dumps(translations)
            )

            return ClientSuccess(
                data=data,
                message=f"Updated translations for language {language}"
            )

        except PoEditorAPIError as e:
            return ClientError(
                error_message=f"Failed to update translations: {e.message}",
                error_code="API_ERROR",
                details={"status_code": e.status_code},
            )
        except Exception as e:
            return ClientError(
                error_message=f"Unexpected error updating translations: {e}",
                error_code="INTERNAL_ERROR",
            )
