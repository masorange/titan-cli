"""Service for PoEditor project operations."""

from titan_cli.core.logging import log_client_operation
from titan_cli.core.result import ClientError, ClientResult, ClientSuccess

from ...exceptions import PoEditorAPIError
from ...models import (
    NetworkPoEditorLanguage,
    NetworkPoEditorProject,
    UIPoEditorProject,
    from_network_project,
)
from ..network import PoEditorNetwork


class ProjectService:
    """Service for PoEditor project operations.

    PRIVATE - only used by PoEditorClient.
    Handles: list, get projects.

    Data flow: Network call → Parse → Map → ClientResult
    """

    def __init__(self, network: PoEditorNetwork):
        """Initialize service with network layer.

        Args:
            network: PoEditorNetwork instance
        """
        self.network = network

    @log_client_operation()
    def list_projects(self) -> ClientResult[list[UIPoEditorProject]]:
        """List all projects accessible to the user.

        Returns:
            ClientResult[List[UIPoEditorProject]]

        The data flow:
            1. Network call to API
            2. Parse response to list of NetworkPoEditorProject
            3. Map each to UIPoEditorProject (formatting + icons)
            4. Wrap in ClientSuccess
        """
        try:
            # 1. Network call
            data = self.network.make_request("projects/list")

            # Handle response
            projects_data = data.get("projects", [])

            # 2. Parse to Network models
            network_projects = [self._parse_project(p) for p in projects_data]

            # 3. Map to UI models (preserving raw response for custom fields)
            ui_projects = [
                from_network_project(p, raw=p_raw)
                for p, p_raw in zip(network_projects, projects_data)
            ]

            # 4. Wrap in Result
            return ClientSuccess(
                data=ui_projects, message=f"Retrieved {len(ui_projects)} projects"
            )

        except PoEditorAPIError as e:
            return ClientError(
                error_message=f"Failed to list projects: {e.message}",
                error_code="API_ERROR",
                details={"status_code": e.status_code},
            )
        except Exception as e:
            return ClientError(
                error_message=f"Unexpected error listing projects: {e}",
                error_code="INTERNAL_ERROR",
            )

    @log_client_operation()
    def get_project(self, project_id: str) -> ClientResult[UIPoEditorProject]:
        """Get project by ID with languages.

        Args:
            project_id: PoEditor project ID

        Returns:
            ClientResult[UIPoEditorProject]
        """
        try:
            # Get project details
            project_data = self.network.make_request("projects/view", id=project_id)

            # Get project languages
            languages_data = self.network.make_request(
                "languages/list", id=project_id
            )

            # Parse project
            network_project = self._parse_project(project_data.get("project", {}))

            # Parse languages
            network_languages = [
                self._parse_language(lang)
                for lang in languages_data.get("languages", [])
            ]

            # Map to UI model
            ui_project = from_network_project(
                network_project,
                languages=network_languages,
                raw=project_data.get("project"),
            )

            return ClientSuccess(
                data=ui_project, message=f"Retrieved project: {ui_project.name}"
            )

        except PoEditorAPIError as e:
            return ClientError(
                error_message=f"Failed to get project {project_id}: {e.message}",
                error_code="API_ERROR",
                details={"status_code": e.status_code},
            )
        except Exception as e:
            return ClientError(
                error_message=f"Unexpected error getting project: {e}",
                error_code="INTERNAL_ERROR",
            )

    def _parse_project(self, data: dict) -> NetworkPoEditorProject:
        """Parse raw API response to network model.

        Args:
            data: Raw project data from API

        Returns:
            NetworkPoEditorProject
        """
        return NetworkPoEditorProject(
            id=str(data.get("id", "")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            created=data.get("created", ""),
            updated=data.get("updated", ""),
            reference_language=data.get("reference_language", ""),
            terms=int(data.get("terms", 0)),
            public=int(data.get("public", 0)),
            open=int(data.get("open", 0)),
            fallback_language=data.get("fallback_language", ""),
        )

    def _parse_language(self, data: dict) -> NetworkPoEditorLanguage:
        """Parse raw API response to network language model.

        Args:
            data: Raw language data from API

        Returns:
            NetworkPoEditorLanguage
        """
        return NetworkPoEditorLanguage(
            code=data.get("code", ""),
            name=data.get("name", ""),
            translations=int(data.get("translations", 0)),
            percentage=float(data.get("percentage", 0.0)),
            updated=data.get("updated", ""),
        )
