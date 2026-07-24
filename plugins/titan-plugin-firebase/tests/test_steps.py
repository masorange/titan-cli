from unittest.mock import MagicMock

from titan_cli.engine import Error, Skip, Success, WorkflowContext
from titan_plugin_firebase.client import RemoteConfigTemplate
from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.exceptions import FirebaseClientError
from titan_plugin_firebase.steps import (
    execute_firebase_login_step,
    execute_firebase_remoteconfig_get_step,
    execute_firebase_status_step,
)


def _ctx(firebase=None, data=None) -> WorkflowContext:
    ctx = WorkflowContext(secrets=MagicMock(), textual=MagicMock(), firebase=firebase)
    ctx.data.update(data or {})
    return ctx


def _firebase_client() -> MagicMock:
    client = MagicMock()
    client.config = FirebasePluginConfig(default_project="default-project")
    client.get_active_account.return_value = "user@example.com"
    client.get_login_command.return_value = "gcloud auth application-default login"
    return client


def test_firebase_login_success() -> None:
    client = _firebase_client()
    client.is_available.return_value = True
    ctx = _ctx(firebase=client)

    result = execute_firebase_login_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_account"] == "user@example.com"


def test_firebase_login_errors_when_auth_missing_by_default() -> None:
    client = _firebase_client()
    client.is_available.return_value = False
    ctx = _ctx(firebase=client)

    result = execute_firebase_login_step(ctx)

    assert isinstance(result, Error)
    assert "application-default login" in result.message
    assert result.recoverable is True


def test_firebase_status_skips_when_auth_missing_and_configured() -> None:
    client = _firebase_client()
    client.is_available.return_value = False
    ctx = _ctx(firebase=client, data={"fail_on_missing_auth": False})

    result = execute_firebase_status_step(ctx)

    assert isinstance(result, Skip)
    assert result.metadata["firebase_login_command"] == (
        "gcloud auth application-default login"
    )


def test_remoteconfig_get_uses_project_id() -> None:
    client = _firebase_client()
    client.get_remote_config.return_value = RemoteConfigTemplate(
        project_id="demo-project",
        template={"version": {"versionNumber": "7"}, "parameters": {}},
        etag="etag-7",
    )
    ctx = _ctx(firebase=client, data={"project_id": "demo-project"})

    result = execute_firebase_remoteconfig_get_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_project_id"] == "demo-project"
    assert result.metadata["firebase_remoteconfig_etag"] == "etag-7"
    assert result.metadata["firebase_remoteconfig_version"] == {"versionNumber": "7"}
    client.get_remote_config.assert_called_once_with("demo-project")


def test_remoteconfig_get_uses_default_project() -> None:
    client = _firebase_client()
    client.get_remote_config.return_value = RemoteConfigTemplate(
        project_id="default-project",
        template={},
        etag=None,
    )
    ctx = _ctx(firebase=client)

    result = execute_firebase_remoteconfig_get_step(ctx)

    assert isinstance(result, Success)
    client.get_remote_config.assert_called_once_with("default-project")


def test_remoteconfig_get_errors_without_project() -> None:
    client = _firebase_client()
    client.config = FirebasePluginConfig()
    ctx = _ctx(firebase=client)

    result = execute_firebase_remoteconfig_get_step(ctx)

    assert isinstance(result, Error)
    assert "project_id is required" in result.message


def test_remoteconfig_get_maps_client_error() -> None:
    client = _firebase_client()
    client.get_remote_config.side_effect = FirebaseClientError("permission denied")
    ctx = _ctx(firebase=client, data={"project_id": "demo-project"})

    result = execute_firebase_remoteconfig_get_step(ctx)

    assert isinstance(result, Error)
    assert "permission denied" in result.message
