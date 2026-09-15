"""Firebase project targets: one brand/environment pair resolved to a project."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class FirebaseProjectTarget(BaseModel):
    """A Firebase project resolved for one brand/environment target."""

    project_id: str = Field(..., description="Firebase project ID.")
    brand: Optional[str] = Field(None, description="Brand owning the project.")
    environment: Optional[str] = Field(
        None,
        description="Logical environment for the project.",
    )
    label: Optional[str] = Field(None, description="Display label.")

    @field_validator("project_id")
    @classmethod
    def normalize_project_id(cls, value: str) -> str:
        """Normalize Firebase project IDs."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("project_id is required")
        return stripped

    @field_validator("brand", "environment", "label")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        """Normalize optional target fields."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def default_label(self) -> "FirebaseProjectTarget":
        """Default the display label from brand and environment."""
        if self.label is None:
            parts = [part for part in (self.brand, self.environment) if part]
            self.label = "/".join(parts) or self.project_id
        return self

    def reference(self) -> str:
        """Return a stable user-facing reference for this target."""
        if self.label and self.label != self.project_id:
            return f"{self.label} ({self.project_id})"
        return self.project_id
