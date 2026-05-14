"""UI-optimized view models for displaying PoEditor data."""

from dataclasses import dataclass


@dataclass
class UIPoEditorLanguage:
    """UI model for a language in a PoEditor project.

    All fields are pre-formatted for display.
    """

    code: str
    name: str
    translations: int
    percentage: float
    progress_icon: str
    formatted_updated_at: str


@dataclass
class UIPoEditorProject:
    """UI model for displaying a PoEditor project.

    All fields are pre-formatted and ready for widget rendering.
    Computed/derived fields are calculated once during construction.
    """

    id: str
    name: str
    description: str
    terms_count: int
    reference_language: str
    progress_icon: str
    formatted_created_at: str
    formatted_updated_at: str
    is_public: bool
    is_open: bool
    fallback_language: str
    raw: dict | None = None


@dataclass
class TermsAddResult:
    """Result of adding terms to a project.

    Contains statistics about the terms operation.
    """

    parsed: int
    added: int


@dataclass
class TermsWithTranslationsResult:
    """Result of creating terms with translations.

    Contains statistics about the operation.
    """

    terms_added: int
    languages_updated: int
