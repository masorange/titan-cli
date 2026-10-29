"""
Network models for GitHub Actions workflow runs and jobs, as `gh api` returns them.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class NetworkWorkflowRun:
    """One element of `workflow_runs` in `GET /repos/{repo}/actions/runs`."""
    id: int
    name: str
    display_title: str
    event: str
    status: str  # "queued", "in_progress", "completed"...
    conclusion: Optional[str]  # "success", "failure", "cancelled"... None while it runs
    head_branch: str
    html_url: str
    run_number: int = 0
    created_at: str = ""
    run_started_at: str = ""
    updated_at: str = ""
    actor_login: str = ""

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "NetworkWorkflowRun":
        return cls(
            id=int(data["id"]),
            name=data.get("name") or "",
            display_title=data.get("display_title") or "",
            event=data.get("event") or "",
            status=data.get("status") or "",
            conclusion=data.get("conclusion"),
            head_branch=data.get("head_branch") or "",
            html_url=data.get("html_url") or "",
            run_number=int(data.get("run_number") or 0),
            created_at=data.get("created_at") or "",
            run_started_at=data.get("run_started_at") or "",
            updated_at=data.get("updated_at") or "",
            actor_login=(data.get("actor") or {}).get("login") or "",
        )


@dataclass
class NetworkWorkflowJob:
    """One element of `jobs` in `GET /repos/{repo}/actions/runs/{id}/jobs`."""
    id: int
    name: str
    status: str
    conclusion: Optional[str]
    html_url: str = ""

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "NetworkWorkflowJob":
        return cls(
            id=int(data["id"]),
            name=data.get("name") or "",
            status=data.get("status") or "",
            conclusion=data.get("conclusion"),
            html_url=data.get("html_url") or "",
        )
