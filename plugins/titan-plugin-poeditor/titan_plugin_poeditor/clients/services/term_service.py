"""Service for PoEditor term and translation operations."""

from titan_cli.core.logging import log_client_operation
from titan_cli.core.result import ClientError, ClientResult, ClientSuccess

from ...exceptions import PoEditorAPIError
from ...models.view import TermsAddResult, TermsWithTranslationsResult
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
    def get_project_languages(self, project_id: str) -> ClientResult[list[str]]:
        """Get all language codes for a project.

        Args:
            project_id: PoEditor project ID

        Returns:
            ClientResult with list of language codes (e.g., ["en", "es", "fr"]) or error
        """
        try:
            data = self.network.make_request("languages/list", id=project_id)

            languages_data = data.get("languages", [])
            language_codes = [lang.get("code") for lang in languages_data if lang.get("code")]

            return ClientSuccess(
                data=language_codes,
                message=f"Retrieved {len(language_codes)} languages"
            )

        except PoEditorAPIError as e:
            return ClientError(
                error_message=f"Failed to fetch languages: {e.message}",
                error_code="API_ERROR",
                details={"status_code": e.status_code},
            )
        except Exception as e:
            return ClientError(
                error_message=f"Unexpected error fetching languages: {e}",
                error_code="INTERNAL_ERROR",
            )

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
    def add_terms(self, project_id: str, terms: list[dict]) -> ClientResult["TermsAddResult"]:
        """Add terms to project following POEditor API v2 specification.

        Adds new terms to a localization project.
        Follows https://poeditor.com/docs/api#terms_add

        Args:
            project_id: PoEditor project ID
            terms: List of term objects. Each object can contain:
                - term (str): The text string - REQUIRED
                - context (str, optional): Contextual information
                - reference (str, optional): Location reference
                - plural (str, optional): Plural form
                - comment (str, optional): Translator notes
                - tags (list|str, optional): Array or string of tag names

        Returns:
            ClientResult[TermsAddResult] with add statistics:
                - parsed (int): Number of terms parsed
                - added (int): Number of terms successfully added

        Example:
            >>> result = service.add_terms(
            ...     project_id="7717",
            ...     terms=[
            ...         {"term": "Add new list"},
            ...         {"term": "Home", "context": "navigation", "tags": ["menu"]}
            ...     ]
            ... )
        """
        try:
            import json

            # Validate terms list
            if not terms:
                return ClientError(
                    error_message="terms list cannot be empty",
                    error_code="INVALID_PARAMETER"
                )

            # Validate each term has required 'term' field
            for idx, term_obj in enumerate(terms):
                if not isinstance(term_obj, dict):
                    return ClientError(
                        error_message=f"Term at index {idx} must be a dictionary",
                        error_code="INVALID_PARAMETER"
                    )
                if "term" not in term_obj:
                    return ClientError(
                        error_message=f"Term at index {idx} missing required 'term' field",
                        error_code="INVALID_PARAMETER"
                    )

            # Make API request
            data = self.network.make_request(
                "terms/add",
                id=project_id,
                data=json.dumps(terms)
            )

            # Extract statistics from response
            terms_result = data.get("terms", {})
            parsed = terms_result.get("parsed", 0)
            added = terms_result.get("added", 0)

            return ClientSuccess(
                data=TermsAddResult(parsed=parsed, added=added),
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

    def _add_terms(self, project_id: str, terms: list[dict]) -> ClientResult[dict]:
        """DEPRECATED: Use add_terms() instead.

        Internal wrapper for backward compatibility.
        """
        return self.add_terms(project_id, terms)

    def _add_translations(
        self,
        project_id: str,
        language: str,
        translations: list[dict]
    ) -> ClientResult[dict]:
        """Add/update translations for a specific language.

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
