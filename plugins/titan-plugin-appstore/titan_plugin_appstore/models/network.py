"""
Network models - DTOs that match Apple's App Store Connect API responses.

These models are faithful to the API structure and should not be modified
unless Apple changes their API schema.

Reference: https://developer.apple.com/documentation/appstoreconnectapi
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ==================== Shared ====================

class ResourceLinks(BaseModel):
    """Links object in API responses."""
    self_link: Optional[str] = Field(None, alias="self")


class Relationship(BaseModel):
    """Generic relationship object."""
    data: Optional[Dict[str, str]] = None
    links: Optional[ResourceLinks] = None


# ==================== App Models ====================

class AppAttributes(BaseModel):
    """App attributes from API."""
    model_config = ConfigDict(populate_by_name=True)

    name: str
    bundle_id: str = Field(alias="bundleId")
    sku: str
    primary_locale: str = Field(alias="primaryLocale")
    is_or_ever_was_made_for_kids: Optional[bool] = Field(None, alias="isOrEverWasMadeForKids")
    available_in_new_territories: Optional[bool] = Field(None, alias="availableInNewTerritories")


class AppRelationships(BaseModel):
    """App relationships from API."""
    model_config = ConfigDict(populate_by_name=True)

    app_store_versions: Optional[Relationship] = Field(None, alias="appStoreVersions")
    available_territories: Optional[Relationship] = Field(None, alias="availableTerritories")


class AppResponse(BaseModel):
    """
    App resource from App Store Connect API.

    Represents the full response structure for an app.
    """
    type: str  # Always "apps"
    id: str
    attributes: AppAttributes
    relationships: Optional[AppRelationships] = None
    links: Optional[ResourceLinks] = None


# ==================== Version Models ====================

class VersionAttributes(BaseModel):
    """App Store Version attributes from API."""
    model_config = ConfigDict(populate_by_name=True)

    platform: str  # IOS, MAC_OS, TV_OS
    version_string: str = Field(alias="versionString")
    app_store_state: Optional[str] = Field(None, alias="appStoreState")
    copyright: Optional[str] = None
    release_type: Optional[str] = Field(None, alias="releaseType")
    earliest_release_date: Optional[str] = Field(None, alias="earliestReleaseDate")
    downloadable: Optional[bool] = None
    created_date: Optional[str] = Field(None, alias="createdDate")


class VersionRelationships(BaseModel):
    """App Store Version relationships from API."""
    model_config = ConfigDict(populate_by_name=True)

    app: Optional[Relationship] = None
    build: Optional[Relationship] = None
    app_store_version_localizations: Optional[Relationship] = Field(
        None, alias="appStoreVersionLocalizations"
    )


class AppStoreVersionResponse(BaseModel):
    """
    App Store Version resource from API.

    Represents the full response structure for an app version.
    """
    type: str  # Always "appStoreVersions"
    id: str
    attributes: VersionAttributes
    relationships: Optional[VersionRelationships] = None
    links: Optional[ResourceLinks] = None


# ==================== List Response Wrappers ====================

class AppListResponse(BaseModel):
    """Response from /apps endpoint."""
    data: List[AppResponse]
    links: Optional[Dict[str, str]] = None
    meta: Optional[Dict[str, Any]] = None


class VersionListResponse(BaseModel):
    """Response from /appStoreVersions endpoint."""
    data: List[AppStoreVersionResponse]
    links: Optional[Dict[str, str]] = None
    meta: Optional[Dict[str, Any]] = None


# ==================== Error Response ====================

class APIErrorDetail(BaseModel):
    """Error detail from API."""
    status: str
    code: str
    title: str
    detail: str
    source: Optional[Dict[str, str]] = None


class APIErrorResponse(BaseModel):
    """Error response from API."""
    errors: List[APIErrorDetail]


# ==================== Build Models ====================

class BuildAttributes(BaseModel):
    """Build attributes from API."""
    model_config = ConfigDict(populate_by_name=True)

    version: str  # Build version (e.g., "1.2.3")
    uploaded_date: Optional[str] = Field(None, alias="uploadedDate")
    expires_date: Optional[str] = Field(None, alias="expiresDate")
    expired: Optional[bool] = None
    min_os_version: Optional[str] = Field(None, alias="minOsVersion")
    icon_asset_token: Optional[Dict[str, Any]] = Field(None, alias="iconAssetToken")
    processing_state: Optional[str] = Field(None, alias="processingState")
    use_s_supported: Optional[bool] = Field(None, alias="usesNonExemptEncryption")


class BuildRelationships(BaseModel):
    """Build relationships from API."""
    model_config = ConfigDict(populate_by_name=True)

    app: Optional[Relationship] = None
    app_store_version: Optional[Relationship] = Field(None, alias="appStoreVersion")
    pre_release_version: Optional[Relationship] = Field(None, alias="preReleaseVersion")


class BuildResponse(BaseModel):
    """
    Build resource from App Store Connect API.

    Represents a build uploaded via Xcode or CI/CD.
    """
    type: str  # Always "builds"
    id: str
    attributes: BuildAttributes
    relationships: Optional[BuildRelationships] = None
    links: Optional[ResourceLinks] = None


class BuildListResponse(BaseModel):
    """Response from /builds endpoint."""
    data: List[BuildResponse]
    links: Optional[Dict[str, str]] = None
    meta: Optional[Dict[str, Any]] = None


# ==================== Localization Models ====================

class LocalizationAttributes(BaseModel):
    """App Store Version Localization attributes from API."""
    model_config = ConfigDict(populate_by_name=True)

    locale: str  # e.g., "es-ES", "en-US"
    description: Optional[str] = None
    keywords: Optional[str] = None
    marketing_url: Optional[str] = Field(None, alias="marketingUrl")
    promotional_text: Optional[str] = Field(None, alias="promotionalText")
    support_url: Optional[str] = Field(None, alias="supportUrl")
    whats_new: Optional[str] = Field(None, alias="whatsNew")


class LocalizationRelationships(BaseModel):
    """Localization relationships from API."""
    model_config = ConfigDict(populate_by_name=True)

    app_store_version: Optional[Relationship] = Field(None, alias="appStoreVersion")


class LocalizationResponse(BaseModel):
    """
    App Store Version Localization resource from API.

    Represents localized metadata for a specific version.
    """
    type: str  # Always "appStoreVersionLocalizations"
    id: str
    attributes: LocalizationAttributes
    relationships: Optional[LocalizationRelationships] = None
    links: Optional[ResourceLinks] = None


class LocalizationListResponse(BaseModel):
    """Response from /appStoreVersionLocalizations endpoint."""
    data: List[LocalizationResponse]
    links: Optional[Dict[str, str]] = None
    meta: Optional[Dict[str, Any]] = None
