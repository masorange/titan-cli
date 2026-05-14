"""Service for PoEditor file upload operations."""

from pathlib import Path

import requests

from titan_cli.core.logging import log_client_operation
from titan_cli.core.result import ClientError, ClientResult, ClientSuccess

from ...exceptions import PoEditorAPIError
from ...models.network.rest import NetworkUploadStats
from ..network import PoEditorNetwork


class UploadService:
    """Service for PoEditor file upload operations.

    PRIVATE - only used by PoEditorClient.
    Handles: upload translation files.
    """

    def __init__(self, network: PoEditorNetwork):
        """Initialize service with network layer.

        Args:
            network: PoEditorNetwork instance
        """
        self.network = network

    @log_client_operation()
    def upload_file(
        self,
        project_id: str,
        file_path: str,
        language_code: str,
        updating: str = "terms_translations",
    ) -> ClientResult[NetworkUploadStats]:
        """Upload translation file to PoEditor project.

        Args:
            project_id: PoEditor project ID
            file_path: Path to translation file
            language_code: Language code (e.g., "en", "es", "fr")
            updating: What to update - "terms", "terms_translations", or "translations"

        Returns:
            ClientResult[NetworkUploadStats] with upload statistics
        """
        try:
            # Validate file exists and is a file
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return ClientError(
                    error_message=f"File not found: {file_path}",
                    error_code="FILE_NOT_FOUND",
                )
            if not file_path_obj.is_file():
                return ClientError(
                    error_message=f"Path is not a file: {file_path}",
                    error_code="INVALID_FILE_PATH",
                )

            # PoEditor file upload requires multipart/form-data
            # Must use requests directly for file upload
            url = f"{self.network.base_url}/projects/upload"

            with open(file_path_obj, "rb") as f:
                files = {"file": (file_path_obj.name, f)}
                data = {
                    "api_token": self.network.api_token,
                    "id": project_id,
                    "language": language_code,
                    "updating": updating,
                }

                response = requests.post(
                    url, data=data, files=files, timeout=self.network.timeout
                )

                response.raise_for_status()

                # Parse response
                json_response = response.json() if response.content else {}

                # Check API-level status
                api_response = json_response.get("response", {})
                if api_response.get("status") == "fail":
                    error_message = api_response.get("message", "Unknown API error")
                    error_code = api_response.get("code", "UNKNOWN")
                    return ClientError(
                        error_message=f"Upload failed: {error_message}",
                        error_code=error_code,
                    )

                # Extract upload statistics
                result = json_response.get("result", {})

                # Get stats from correct section based on updating mode
                if updating == "translations":
                    stats_source = result.get("translations", {})
                else:
                    # For "terms" or "terms_translations", use terms section
                    stats_source = result.get("terms", {})

                upload_stats = NetworkUploadStats(
                    added=stats_source.get("added", 0),
                    updated=stats_source.get("updated", 0),
                    deleted=stats_source.get("deleted", 0),
                )

                return ClientSuccess(
                    data=upload_stats,
                    message=f"Uploaded to project {project_id}: {upload_stats.added} added, {upload_stats.updated} updated",
                )

        except PoEditorAPIError as e:
            return ClientError(
                error_message=f"Failed to upload file: {e.message}",
                error_code="API_ERROR",
                details={"status_code": e.status_code},
            )
        except requests.exceptions.RequestException as e:
            return ClientError(
                error_message=f"Upload request failed: {e}", error_code="UPLOAD_ERROR"
            )
        except Exception as e:
            return ClientError(
                error_message=f"Unexpected error uploading file: {e}",
                error_code="INTERNAL_ERROR",
            )
