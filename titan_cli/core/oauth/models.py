"""Provider-neutral OAuth data models."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import time
from typing import Any, Mapping, Sequence


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_values(values: Sequence[str] | str | None) -> tuple[str, ...]:
    if not values:
        return ()
    if isinstance(values, str):
        values = (values,)
    return tuple(sorted({value.strip() for value in values if value and value.strip()}))


@dataclass(frozen=True)
class OAuthRequest:
    """A provider-neutral request for an OAuth credential."""

    provider: str
    connection_id: str
    scopes: Sequence[str] = field(default_factory=tuple)
    interactive: bool = False
    access_token_env_var: str | None = None
    legacy_secret_keys: Sequence[str] = field(default_factory=tuple)
    subject: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", self.provider.strip().lower())
        object.__setattr__(self, "connection_id", self.connection_id.strip())
        object.__setattr__(self, "scopes", _normalize_values(self.scopes))
        object.__setattr__(
            self,
            "legacy_secret_keys",
            _normalize_values(self.legacy_secret_keys),
        )
        object.__setattr__(
            self,
            "access_token_env_var",
            _normalize_optional(self.access_token_env_var),
        )
        object.__setattr__(self, "subject", _normalize_optional(self.subject))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

        if not self.provider:
            raise ValueError("OAuth provider is required.")
        if not self.connection_id:
            raise ValueError("OAuth connection_id is required.")


@dataclass(frozen=True)
class OAuthTokenSet:
    """Stored OAuth token data."""

    access_token: str
    refresh_token: str | None = None
    expires_at: int | None = None
    token_type: str = "Bearer"
    scopes: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "access_token", self.access_token.strip())
        object.__setattr__(self, "refresh_token", _normalize_optional(self.refresh_token))
        object.__setattr__(self, "token_type", self.token_type.strip() or "Bearer")
        object.__setattr__(self, "scopes", _normalize_values(self.scopes))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def is_valid(
        self,
        *,
        now: int | None = None,
        refresh_margin_seconds: int = 300,
    ) -> bool:
        """Return whether the access token can be used without refresh."""
        if not self.access_token:
            return False
        if self.expires_at is None:
            return True
        current_time = int(time.time()) if now is None else now
        return self.expires_at > current_time + refresh_margin_seconds

    def to_dict(self) -> dict[str, Any]:
        """Serialize token data for SecretManager storage."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "token_type": self.token_type,
            "scopes": list(self.scopes),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "OAuthTokenSet":
        """Build a token set from SecretManager storage."""
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token.strip():
            raise ValueError("Stored OAuth token set is missing access_token.")

        expires_at_raw = payload.get("expires_at")
        expires_at = int(expires_at_raw) if expires_at_raw is not None else None

        scopes_raw = payload.get("scopes")
        scopes = scopes_raw if isinstance(scopes_raw, list) else ()

        metadata_raw = payload.get("metadata")
        metadata = metadata_raw if isinstance(metadata_raw, dict) else {}

        return cls(
            access_token=access_token,
            refresh_token=payload.get("refresh_token"),
            expires_at=expires_at,
            token_type=str(payload.get("token_type") or "Bearer"),
            scopes=scopes,
            metadata=metadata,
        )


@dataclass(frozen=True)
class OAuthCredential:
    """Resolved credential returned to callers."""

    access_token: str
    provider: str
    connection_id: str
    credential_key: str
    source: str
    token_type: str = "Bearer"
    expires_at: int | None = None
    scopes: Sequence[str] = field(default_factory=tuple)


def build_oauth_credential_key(request: OAuthRequest) -> str:
    """Build a stable, non-secret credential key for an OAuth request."""
    provider_label = "".join(
        char if char.isalnum() else "_"
        for char in request.provider.lower()
    ).strip("_") or "oauth"
    material = {
        "provider": request.provider,
        "connection_id": request.connection_id,
        "scopes": list(request.scopes),
        "subject": request.subject,
    }
    encoded = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()[:32]
    return f"{provider_label}_{digest}"
