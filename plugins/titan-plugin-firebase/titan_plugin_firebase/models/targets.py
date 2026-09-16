"""A Firebase project a workflow acts on."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class FirebaseProjectTarget(BaseModel):
    """
    One Firebase project, with optional context for display and filtering.

    The label exists so a caller that has a better name for a project — a
    brand, a team, an environment — can have it shown in tables and prompts.
    Brand, environment and groups are generic metadata from configuration or
    an earlier workflow step; the plugin treats them as labels, not as Firebase
    concepts.
    """

    project_id: str = Field(..., description="Firebase project ID.")
    label: Optional[str] = Field(None, description="Display label.")
    brand: Optional[str] = Field(None, description="Business brand or app family.")
    environment: Optional[str] = Field(
        None,
        description="Deployment environment such as dev or pro.",
    )
    groups: list[str] = Field(
        default_factory=list,
        description="Generic project-set group tags.",
    )

    @field_validator("project_id")
    @classmethod
    def normalize_project_id(cls, value: str) -> str:
        """Normalize Firebase project IDs."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("project_id is required")
        return stripped

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: Optional[str]) -> Optional[str]:
        """Normalize the optional display label."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("brand")
    @classmethod
    def normalize_brand(cls, value: Optional[str]) -> Optional[str]:
        """Normalize the optional brand label."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("environment")
    @classmethod
    def normalize_environment(cls, value: Optional[str]) -> Optional[str]:
        """Normalize environment names for deterministic filtering."""
        if value is None:
            return None
        stripped = value.strip().casefold()
        return stripped or None

    @field_validator("groups", mode="before")
    @classmethod
    def normalize_groups(cls, value: Any) -> Any:
        """Accept one group or many, preserving first-seen order."""
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return value
        groups: list[str] = []
        for item in value:
            if isinstance(item, str):
                group = item.strip().casefold()
                if group and group not in groups:
                    groups.append(group)
        return groups

    @model_validator(mode="after")
    def default_label(self) -> "FirebaseProjectTarget":
        """Fall back to the project ID as its own label."""
        if self.label is None:
            self.label = self.project_id
        return self

    def reference(self) -> str:
        """Return a stable user-facing reference for this target."""
        if self.label and self.label != self.project_id:
            return f"{self.label} ({self.project_id})"
        return self.project_id

    def context_fields(self) -> list[str]:
        """Return compact target context for tables and prompts."""
        fields: list[str] = []
        if self.environment:
            fields.append(self.environment.upper())
        if self.brand:
            fields.append(self.brand)
        if self.groups:
            fields.append(", ".join(self.groups))
        return fields
