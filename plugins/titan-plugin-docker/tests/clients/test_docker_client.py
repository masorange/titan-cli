import json
from unittest.mock import patch

from titan_cli.core.result import ClientSuccess, ClientError
from titan_cli.core.plugins.models import DockerBuildTargetConfig
from titan_plugin_docker.clients.docker_client import DockerClient
from titan_plugin_docker.exceptions import DockerCommandError


def _make_client(**kwargs) -> DockerClient:
    with patch("shutil.which", return_value="/usr/bin/docker"):
        return DockerClient(**kwargs)


def test_compose_up_delegates_to_compose_service() -> None:
    client = _make_client()

    with patch.object(client.network, "run_command", return_value="") as run_command:
        result = client.compose_up(services=["db"])

    assert isinstance(result, ClientSuccess)
    assert result.data == ["db"]
    args = run_command.call_args.args[0]
    assert args[:4] == ["docker", "compose", "-f", "docker-compose.yml"]
    assert args[-1] == "db"


def test_compose_up_wraps_command_failures() -> None:
    client = _make_client()

    with patch.object(client.network, "run_command", side_effect=DockerCommandError("boom")):
        result = client.compose_up()

    assert isinstance(result, ClientError)
    assert result.error_code == "COMPOSE_UP_ERROR"


def test_compose_status_parses_json_array() -> None:
    client = _make_client()
    ps_output = json.dumps([
        {"Service": "db", "Name": "postgres_container", "Image": "pgvector/pgvector:pg17", "State": "running", "Status": "Up 2 hours", "Health": "healthy"},
        {"Service": "backend", "Name": "backend_container", "Image": "economy-backend", "State": "exited", "Status": "Exited (1)", "Health": ""},
    ])

    with patch.object(client.network, "run_command", return_value=ps_output):
        result = client.compose_status()

    assert isinstance(result, ClientSuccess)
    assert result.data.summary == "1/2 running"
    assert result.data.all_running is False
    assert [s.service for s in result.data.services] == ["db", "backend"]


def test_list_services_parses_newline_output() -> None:
    client = _make_client()

    with patch.object(client.network, "run_command", return_value="db\nbackend\nfrontend\n") as run_command:
        result = client.list_services()

    assert isinstance(result, ClientSuccess)
    assert result.data == ["db", "backend", "frontend"]
    args = run_command.call_args.args[0]
    assert args == ["docker", "compose", "-f", "docker-compose.yml", "config", "--services"]


def test_list_services_wraps_command_failures() -> None:
    client = _make_client()

    with patch.object(client.network, "run_command", side_effect=DockerCommandError("boom")):
        result = client.list_services()

    assert isinstance(result, ClientError)
    assert result.error_code == "COMPOSE_LIST_SERVICES_ERROR"


def test_build_target_delegates_to_build_service() -> None:
    client = _make_client()
    target = DockerBuildTargetConfig(
        name="frontend",
        dockerfile="packages/frontend/Dockerfile",
        image="ghcr.io/finxo/economy-frontend",
        target="production",
        push=True,
    )

    with patch.object(client.network, "run_command", return_value="") as run_command:
        result = client.build_target(target)

    assert isinstance(result, ClientSuccess)
    assert result.data.image_ref == "ghcr.io/finxo/economy-frontend:latest"
    assert result.data.pushed is True
    args = run_command.call_args.args[0]
    assert args[:3] == ["docker", "buildx", "build"]
    assert "--push" in args
    assert "--target" in args and "production" in args
