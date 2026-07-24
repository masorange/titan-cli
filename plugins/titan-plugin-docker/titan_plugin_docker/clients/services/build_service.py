# plugins/titan-plugin-docker/titan_plugin_docker/clients/services/build_service.py
"""
Build Service

Business logic for building (and optionally pushing) Docker images.
Uses network layer to execute commands, parses to network models, maps to view models.
"""
from titan_cli.core.result import ClientResult, ClientSuccess, ClientError
from titan_cli.core.logging import log_client_operation
from titan_cli.core.plugins.models import DockerBuildTargetConfig

from ..network import DockerNetwork
from ...models.network.build_result import NetworkBuildResult
from ...models.view.build_result import UIBuildResult
from ...models.mappers import from_network_build_result
from ...exceptions import DockerCommandError


class BuildService:
    """
    Service for building and pushing Docker images.

    Operates on a single `DockerBuildTargetConfig` at a time - the caller
    (operations layer) decides which target(s) to build.
    """

    def __init__(self, docker_network: DockerNetwork):
        """
        Initialize Build service.

        Args:
            docker_network: DockerNetwork instance for command execution
        """
        self.docker = docker_network

    @log_client_operation()
    def build_target(self, target: DockerBuildTargetConfig) -> ClientResult[UIBuildResult]:
        """
        Build (and optionally push) a single configured image.

        Uses `docker buildx build` so a single code path covers both
        single-platform and multi-platform builds.

        Args:
            target: Build target configuration

        Returns:
            ClientResult[UIBuildResult]
        """
        try:
            image_ref = f"{target.image}:{target.tag}"

            args = [
                "docker", "buildx", "build",
                "--platform", target.platforms,
                "-t", image_ref,
                "-f", target.dockerfile,
            ]
            if target.target:
                args.extend(["--target", target.target])
            if target.push:
                args.append("--push")
            args.append(target.context)

            self.docker.run_command(args)

            network_result = NetworkBuildResult(
                name=target.name,
                image=target.image,
                tag=target.tag,
                platforms=target.platforms,
                target=target.target or "",
                pushed=target.push,
            )
            ui_result = from_network_build_result(network_result)

            return ClientSuccess(data=ui_result, message=f"Built {image_ref}")
        except DockerCommandError as e:
            return ClientError(error_message=str(e), error_code="BUILD_ERROR")
