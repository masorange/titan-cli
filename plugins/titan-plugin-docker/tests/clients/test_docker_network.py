from unittest.mock import patch

import pytest

from titan_plugin_docker.clients.network.docker_network import DockerNetwork
from titan_plugin_docker.exceptions import DockerCommandError


@pytest.fixture
def network() -> DockerNetwork:
    with patch("shutil.which", return_value="/usr/bin/docker"):
        return DockerNetwork()


def test_stream_command_invokes_on_line_for_each_line(network: DockerNetwork) -> None:
    lines = []

    output = network.stream_command(["python3", "-c", "print('a'); print('b')"], on_line=lines.append)

    assert lines == ["a", "b"]
    assert output == "a\nb"


def test_stream_command_raises_on_nonzero_exit(network: DockerNetwork) -> None:
    with pytest.raises(DockerCommandError):
        network.stream_command(
            ["python3", "-c", "import sys; print('boom'); sys.exit(1)"],
            on_line=lambda line: None,
        )


def test_stream_command_check_false_does_not_raise(network: DockerNetwork) -> None:
    output = network.stream_command(
        ["python3", "-c", "import sys; print('boom'); sys.exit(1)"],
        on_line=lambda line: None,
        check=False,
    )

    assert output == "boom"
