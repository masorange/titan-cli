"""A Firebase project a workflow acts on."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class FirebaseProjectTarget(BaseModel):
    """
    One Firebase project, with an optional label for display.

    The label exists so a caller that has a better name for a project — a
    brand, a team, an environment — can have it shown in tables and prompts
    without this plugin needing to know what that name means.
    """

    project_id: str = Field(..., description="Firebase project ID.")
    label: Optional[str] = Field(None, description="Display label.")

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
