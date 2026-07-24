# plugins/titan-plugin-docker/titan_plugin_docker/clients/network/docker_network.py
"""
Docker Network Client

Low-level Docker CLI command executor.
Handles subprocess execution and error handling.
No model conversion - returns raw command output strings.
"""
import subprocess
import shutil
import time
from typing import List, Optional

from titan_cli.core.logging.config import get_logger

from ...exceptions import DockerError, DockerClientError, DockerCommandError


class DockerNetwork:
    """
    Docker network client using the Docker CLI (docker, docker compose, docker buildx).

    Executes commands and handles errors.
    Returns raw command output (strings) without parsing or model conversion.
    """

    def __init__(self, project_path: str = "."):
        """
        Initialize Docker network client.

        Args:
            project_path: Path to the project root (default: current directory)

        Raises:
            DockerClientError: If the Docker CLI is not installed
        """
        self.project_path = project_path
        self._logger = get_logger(__name__)
        self._check_docker_installed()

    def _check_docker_installed(self) -> None:
        """
        Check if the Docker CLI is installed.

        Raises:
            DockerClientError: If docker is not found
        """
        if not shutil.which("docker"):
            raise DockerClientError("Docker CLI not found. Please install Docker.")

    def run_command(
        self,
        args: List[str],
        check: bool = True,
        cwd: Optional[str] = None,
    ) -> str:
        """
        Run a docker CLI command and return stdout.

        Args:
            args: Full command arguments (including 'docker')
            check: Raise exception on non-zero exit code (default: True)
            cwd: Optional working directory (overrides project_path)

        Returns:
            Command stdout as string

        Raises:
            DockerCommandError: If the command fails
            DockerClientError: If the docker CLI is not found
            DockerError: If an unexpected error occurs
        """
        subcommand = " ".join(args[1:3]) if len(args) > 1 else "unknown"
        start = time.time()

        try:
            result = subprocess.run(
                args,
                cwd=cwd or self.project_path,
                capture_output=True,
                text=True,
                check=check,
            )
            self._logger.debug(
                "docker_command_ok",
                subcommand=subcommand,
                duration=round(time.time() - start, 3),
            )
            return result.stdout.rstrip()
        except subprocess.CalledProcessError as e:
            self._logger.debug(
                "docker_command_failed",
                subcommand=subcommand,
                duration=round(time.time() - start, 3),
                exit_code=e.returncode,
            )
            error_msg = e.stderr.strip() if e.stderr else str(e)
            raise DockerCommandError(f"Docker command failed: {error_msg}") from e
        except FileNotFoundError:
            raise DockerClientError("Docker CLI not found. Please install Docker.")
        except Exception as e:
            raise DockerError(f"An unexpected error occurred: {e}") from e

    def get_project_path(self) -> str:
        """
        Get configured project path.

        Returns:
            Project path string
        """
        return self.project_path
