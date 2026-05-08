"""Network models for PoEditor REST API - faithful to API responses."""

from dataclasses import dataclass


@dataclass
class NetworkPoEditorLanguage:
    """PoEditor REST API language response."""

    code: str
    name: str
    translations: int = 0
    percentage: float = 0.0
    updated: str = ""


@dataclass
class NetworkPoEditorProject:
    """PoEditor REST API project response - faithful to API structure.

    Fields match PoEditor API response exactly.
    """

    id: str
    name: str
    description: str = ""
    created: str = ""
    updated: str = ""
    reference_language: str = ""
    terms: int = 0
    public: int = 0
    open: int = 0
    fallback_language: str = ""
