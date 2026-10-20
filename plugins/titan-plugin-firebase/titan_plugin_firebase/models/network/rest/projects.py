"""Network models for the Firebase Management projects list."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class NetworkFirebaseProject(BaseModel):
    """One FirebaseProject from the Management REST API."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    project_id: str = Field(..., alias="projectId")
    display_name: Optional[str] = Field(None, alias="displayName")
    name: Optional[str] = None
    project_number: Optional[str] = Field(None, alias="projectNumber")


class NetworkFirebaseProjectsPage(BaseModel):
    """One paginated Firebase projects response."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    results: list[NetworkFirebaseProject] = Field(default_factory=list)
    next_page_token: Optional[str] = Field(None, alias="nextPageToken")
