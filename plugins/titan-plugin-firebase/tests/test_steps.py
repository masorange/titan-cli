from unittest.mock import MagicMock

import pytest

from titan_cli.engine import Error, Skip, Success, WorkflowContext
from titan_plugin_firebase.client import RemoteConfigTemplate
from titan_plugin_firebase.config import FirebasePluginConfig
from titan_plugin_firebase.exceptions import (
    FirebaseAuthRejectedError,
    FirebaseClientError,
)
from titan_plugin_firebase.models import (
    FirebaseProjectTarget,
    RemoteConfigInventory,
    RemoteConfigKeyInventory,
    RemoteConfigProjectInventory,
)
from titan_plugin_firebase.steps import (
    execute_firebase_login_step,
    execute_firebase_remoteconfig_get_step,
    execute_firebase_remoteconfig_inventory_step,
    execute_firebase_status_step,
)


def _ctx(firebase=None, data=None) -> WorkflowContext:
    textual = MagicMock()
    textual.ask_text.return_value = None
    textual.ask_password.return_value = None
    ctx = WorkflowContext(secrets=MagicMock(), textual=textual, firebase=firebase)
    ctx.data.update(data or {})
    return ctx


def _firebase_client() -> MagicMock:
    client = MagicMock()
    client.config = FirebasePluginConfig(default_project="default-project")
    client.get_active_account.return_value = "user@example.com"
    client.get_login_command.return_value = "gcloud auth application-default login"
    return client


def _save_oauth_client_id_mock(client: MagicMock):
    """Return a mock side effect that enables OAuth on fake Firebase clients."""

    def _save(client_id: str, client_secret: str | None = None) -> None:
        client.config = client.config.model_copy(
            update={
                "oauth_client_id": client_id,
                "oauth_client_secret": client_secret,
            }
        )

    return _save


def test_firebase_login_success() -> None:
    client = _firebase_client()
    client.is_available.return_value = True
    client.get_access_token_source_label.return_value = "gcloud ADC"
    ctx = _ctx(firebase=client)

    result = execute_firebase_login_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_account"] is None
    assert result.metadata["firebase_auth_source"] == "gcloud ADC"
    assert result.metadata["firebase_access_token_saved"] is False
    assert result.metadata["firebase_oauth_login_completed"] is False
    client.get_active_account.assert_not_called()
    ctx.textual.success_text.assert_called_with(
        "Firebase auth available via gcloud ADC"
    )


def test_firebase_login_uses_google_oauth_when_configured() -> None:
    client = _firebase_client()
    client.config = FirebasePluginConfig(
        default_project="default-project",
        oauth_client_id="google-client-id",
    )
    client.is_available.side_effect = [False, True]
    client.get_access_token.return_value = "oauth-token"
    client.get_access_token_source_label.return_value = "Titan OAuth token store"
    ctx = _ctx(firebase=client)

    result = execute_firebase_login_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_account"] is None
    assert result.metadata["firebase_auth_source"] == "Titan OAuth token store"
    assert result.metadata["firebase_access_token_saved"] is True
    assert result.metadata["firebase_oauth_login_completed"] is True
    client.get_access_token.assert_called_once()
    assert client.get_access_token.call_args.kwargs["interactive"] is True
    ctx.textual.ask_password.assert_not_called()


def test_firebase_login_prompts_client_pair_when_google_rejects_secret() -> None:
    client = _firebase_client()
    client.config = FirebasePluginConfig(
        default_project="default-project",
        oauth_client_id="stale-client-id",
    )
    client.is_available.side_effect = [False, True]
    client.get_access_token.side_effect = [
        FirebaseClientError(
            "Firebase OAuth credential resolution failed: "
            "Google OAuth exchange failed: The provided client secret is invalid."
        ),
        "oauth-token",
    ]
    client.get_access_token_source_label.return_value = "Titan OAuth token store"
    client.save_oauth_client_id.side_effect = _save_oauth_client_id_mock(client)
    ctx = _ctx(firebase=client)
    ctx.textual.ask_text.return_value = " desktop-client-id "
    ctx.textual.ask_password.return_value = " desktop-client-secret "

    result = execute_firebase_login_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_oauth_login_completed"] is True
    client.delete_oauth_client_id.assert_not_called()
    client.save_oauth_client_id.assert_called_once_with(
        "desktop-client-id",
        client_secret="desktop-client-secret",
    )
    assert client.get_access_token.call_count == 2
    ctx.textual.ask_text.assert_called_once()
    ctx.textual.ask_password.assert_called_once()
    warning_messages = [
        call.args[0] for call in ctx.textual.warning_text.call_args_list
    ]
    assert any("client secret" in msg.lower() for msg in warning_messages)


def test_firebase_login_prompts_and_saves_token_when_auth_missing() -> None:
    client = _firebase_client()
    client.is_available.side_effect = [False, True]
    client.get_access_token_source_label.return_value = (
        "keyring:ragnarok-ios_firebase_access_token"
    )
    ctx = _ctx(firebase=client)
    ctx.textual.ask_password.return_value = " ya29.token "

    result = execute_firebase_login_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_access_token_saved"] is True
    assert result.metadata["firebase_oauth_login_completed"] is False
    client.save_access_token.assert_called_once_with("ya29.token")
    ctx.textual.ask_password.assert_called_once()


def test_firebase_login_prompts_oauth_client_id_before_manual_token() -> None:
    client = _firebase_client()
    client.is_available.side_effect = [False, True]
    client.get_access_token.return_value = "oauth-token"
    client.get_access_token_source_label.return_value = "Titan OAuth token store"
    client.save_oauth_client_id.side_effect = _save_oauth_client_id_mock(client)
    ctx = _ctx(firebase=client)
    ctx.textual.ask_text.return_value = " google-client-id "
    ctx.textual.ask_password.return_value = " google-client-secret "

    result = execute_firebase_login_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_access_token_saved"] is True
    assert result.metadata["firebase_oauth_login_completed"] is True
    client.save_oauth_client_id.assert_called_once_with(
        "google-client-id",
        client_secret="google-client-secret",
    )
    client.get_access_token.assert_called_once()
    assert client.get_access_token.call_args.kwargs["interactive"] is True
    ctx.textual.ask_password.assert_called_once()


def test_firebase_login_falls_back_to_manual_token_after_oauth_failure() -> None:
    client = _firebase_client()
    client.config = FirebasePluginConfig(
        default_project="default-project",
        oauth_client_id="google-client-id",
    )
    client.is_available.side_effect = [False, False, True]
    client.get_access_token.side_effect = FirebaseClientError(
        "Firebase Google OAuth login failed: callback timed out"
    )
    client.get_access_token_source_label.return_value = "Titan OAuth token store"
    ctx = _ctx(firebase=client)
    ctx.textual.ask_password.return_value = " ya29.manual-token "

    result = execute_firebase_login_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_access_token_saved"] is True
    assert result.metadata["firebase_oauth_login_completed"] is False
    client.get_access_token.assert_called_once()
    assert client.get_access_token.call_args.kwargs["interactive"] is True
    client.save_access_token.assert_called_once_with("ya29.manual-token")
    warning_messages = [
        call.args[0] for call in ctx.textual.warning_text.call_args_list
    ]
    assert any("did not complete" in msg for msg in warning_messages)


def test_firebase_login_aborts_on_unexpected_oauth_failure() -> None:
    client = _firebase_client()
    client.config = FirebasePluginConfig(
        default_project="default-project",
        oauth_client_id="google-client-id",
    )
    client.is_available.return_value = False
    client.get_access_token.side_effect = RuntimeError("unexpected crash")
    ctx = _ctx(firebase=client)
    ctx.textual.ask_password.return_value = " ya29.manual-token "

    result = execute_firebase_login_step(ctx)

    assert isinstance(result, Error)
    assert "Firebase Google OAuth login failed" in result.message
    client.save_access_token.assert_not_called()


def test_firebase_login_errors_when_auth_missing_and_token_not_entered() -> None:
    client = _firebase_client()
    client.is_available.return_value = False
    ctx = _ctx(firebase=client)

    result = execute_firebase_login_step(ctx)

    assert isinstance(result, Error)
    assert "application-default login" in result.message
    assert result.recoverable is True
    ctx.textual.ask_password.assert_called_once()


def test_firebase_status_does_not_prompt_by_default() -> None:
    client = _firebase_client()
    client.is_available.return_value = False
    ctx = _ctx(firebase=client)

    result = execute_firebase_status_step(ctx)

    assert isinstance(result, Error)
    ctx.textual.ask_password.assert_not_called()


def test_firebase_status_skips_when_auth_missing_and_configured() -> None:
    client = _firebase_client()
    client.is_available.return_value = False
    ctx = _ctx(firebase=client, data={"fail_on_missing_auth": False})

    result = execute_firebase_status_step(ctx)

    assert isinstance(result, Skip)
    assert result.metadata["firebase_account"] is None
    assert result.metadata["firebase_auth_source"] is None
    assert result.metadata["firebase_login_command"] == (
        "gcloud auth application-default login"
    )
    assert result.metadata["firebase_access_token_saved"] is False
    assert result.metadata["firebase_oauth_login_completed"] is False


def test_firebase_status_parses_serialized_false_flag() -> None:
    client = _firebase_client()
    client.is_available.return_value = False
    ctx = _ctx(firebase=client, data={"fail_on_missing_auth": "false"})

    result = execute_firebase_status_step(ctx)

    assert isinstance(result, Skip)
    assert result.metadata["firebase_access_token_saved"] is False


def test_firebase_login_parses_serialized_prompt_false_flag() -> None:
    client = _firebase_client()
    client.is_available.return_value = False
    ctx = _ctx(
        firebase=client,
        data={
            "prompt_for_missing_auth": "false",
            "fail_on_missing_auth": False,
        },
    )

    result = execute_firebase_login_step(ctx)

    assert isinstance(result, Skip)
    ctx.textual.ask_text.assert_not_called()
    ctx.textual.ask_password.assert_not_called()


@pytest.mark.parametrize(
    "flag_value",
    [
        None,
        "eventually",
        [],
    ],
)
def test_firebase_status_rejects_invalid_missing_auth_flag(flag_value) -> None:
    client = _firebase_client()
    client.is_available.return_value = False
    ctx = _ctx(firebase=client, data={"fail_on_missing_auth": flag_value})

    result = execute_firebase_status_step(ctx)

    assert isinstance(result, Error)
    assert "fail_on_missing_auth must be a boolean" in result.message
    client.is_available.assert_not_called()


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


def test_remoteconfig_get_rejects_non_object_template() -> None:
    client = _firebase_client()
    client.get_remote_config.return_value = RemoteConfigTemplate(
        project_id="demo-project",
        template=["not", "an", "object"],
        etag="etag-7",
    )
    ctx = _ctx(firebase=client, data={"project_id": "demo-project"})

    result = execute_firebase_remoteconfig_get_step(ctx)

    assert isinstance(result, Error)
    assert "template must be a JSON object" in result.message
    ctx.textual.success_text.assert_not_called()
    ctx.textual.end_step.assert_called_with("error")


def test_remoteconfig_get_rejects_non_object_version() -> None:
    client = _firebase_client()
    client.get_remote_config.return_value = RemoteConfigTemplate(
        project_id="demo-project",
        template={"version": ["not", "an", "object"], "parameters": {}},
        etag="etag-7",
    )
    ctx = _ctx(firebase=client, data={"project_id": "demo-project"})

    result = execute_firebase_remoteconfig_get_step(ctx)

    assert isinstance(result, Error)
    assert "version must be a JSON object" in result.message
    ctx.textual.success_text.assert_not_called()
    ctx.textual.end_step.assert_called_with("error")


def test_remoteconfig_get_rejects_invalid_version_number_shape() -> None:
    client = _firebase_client()
    client.get_remote_config.return_value = RemoteConfigTemplate(
        project_id="demo-project",
        template={"version": {"versionNumber": ["7"]}, "parameters": {}},
        etag="etag-7",
    )
    ctx = _ctx(firebase=client, data={"project_id": "demo-project"})

    result = execute_firebase_remoteconfig_get_step(ctx)

    assert isinstance(result, Error)
    assert "version.versionNumber must be a string or integer" in result.message
    ctx.textual.success_text.assert_not_called()
    ctx.textual.end_step.assert_called_with("error")


def test_remoteconfig_get_reauthenticates_once_after_rejected_token() -> None:
    client = _firebase_client()
    client.config = FirebasePluginConfig(
        default_project="default-project",
        oauth_client_id="google-client-id",
    )
    client.get_remote_config.side_effect = [
        FirebaseAuthRejectedError(
            "expired token",
            auth_source="keyring:ragnarok-ios_firebase_access_token",
        ),
        RemoteConfigTemplate(
            project_id="demo-project",
            template={"parameters": {}},
            etag="etag-9",
        ),
    ]
    client.invalidate_access_token_source.return_value = True
    client.get_access_token.return_value = "fresh-token"
    client.is_available.return_value = True
    ctx = _ctx(firebase=client, data={"project_id": "demo-project"})

    result = execute_firebase_remoteconfig_get_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_remoteconfig_etag"] == "etag-9"
    assert client.get_remote_config.call_count == 2
    client.invalidate_access_token_source.assert_called_once_with(
        "keyring:ragnarok-ios_firebase_access_token"
    )
    assert client.get_access_token.call_args.kwargs["interactive"] is True


def test_remoteconfig_inventory_uses_configured_targets() -> None:
    client = _firebase_client()
    client.config = FirebasePluginConfig(
        projects=[
            {
                "brand": "yoigo",
                "environment": "prod",
                "project_id": "yoigo-prod",
            }
        ]
    )
    target = FirebaseProjectTarget(
        brand="yoigo",
        environment="prod",
        project_id="yoigo-prod",
    )
    client.get_remote_config_inventory.return_value = RemoteConfigInventory(
        targets=[target],
        projects=[RemoteConfigProjectInventory(target=target, parameter_count=1)],
        keys=[RemoteConfigKeyInventory(key="feature_enabled")],
    )
    ctx = _ctx(firebase=client)

    result = execute_firebase_remoteconfig_inventory_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_remoteconfig_project_count"] == 1
    assert result.metadata["firebase_remoteconfig_key_count"] == 1
    assert result.metadata["firebase_remoteconfig_keys"][0]["key"] == "feature_enabled"
    ctx.textual.table.assert_called_once()
    targets_arg = client.get_remote_config_inventory.call_args.args[0]
    assert targets_arg[0].project_id == "yoigo-prod"


def test_remoteconfig_inventory_errors_without_targets() -> None:
    client = _firebase_client()
    client.config = FirebasePluginConfig()
    ctx = _ctx(firebase=client)

    result = execute_firebase_remoteconfig_inventory_step(ctx)

    assert isinstance(result, Error)
    assert "No Firebase project targets" in result.message


def test_remoteconfig_inventory_errors_when_all_projects_fail() -> None:
    client = _firebase_client()
    client.config = FirebasePluginConfig(projects=["yoigo-prod"])
    target = FirebaseProjectTarget(project_id="yoigo-prod")
    client.get_remote_config_inventory.return_value = RemoteConfigInventory(
        targets=[target],
        failures=[],
    )
    ctx = _ctx(firebase=client)

    result = execute_firebase_remoteconfig_inventory_step(ctx)

    assert isinstance(result, Error)
    assert "could be read" in result.message


def test_remoteconfig_inventory_reauthenticates_once_after_rejected_token() -> None:
    client = _firebase_client()
    client.config = FirebasePluginConfig(
        oauth_client_id="google-client-id",
        projects=["yoigo-prod"],
    )
    target = FirebaseProjectTarget(project_id="yoigo-prod")
    inventory = RemoteConfigInventory(
        targets=[target],
        projects=[RemoteConfigProjectInventory(target=target, parameter_count=1)],
        keys=[RemoteConfigKeyInventory(key="feature_enabled")],
    )
    client.get_remote_config_inventory.side_effect = [
        FirebaseAuthRejectedError(
            "expired token",
            auth_source="keyring:ragnarok-ios_firebase_access_token",
        ),
        inventory,
    ]
    client.invalidate_access_token_source.return_value = True
    client.get_access_token.return_value = "fresh-token"
    client.is_available.return_value = True
    ctx = _ctx(firebase=client)

    result = execute_firebase_remoteconfig_inventory_step(ctx)

    assert isinstance(result, Success)
    assert result.metadata["firebase_remoteconfig_key_count"] == 1
    assert client.get_remote_config_inventory.call_count == 2
    client.invalidate_access_token_source.assert_called_once_with(
        "keyring:ragnarok-ios_firebase_access_token"
    )
    assert client.get_access_token.call_args.kwargs["interactive"] is True


def test_remoteconfig_inventory_prompts_manual_when_oauth_missing() -> None:
    client = _firebase_client()
    client.config = FirebasePluginConfig(projects=["yoigo-prod"])
    target = FirebaseProjectTarget(project_id="yoigo-prod")
    inventory = RemoteConfigInventory(
        targets=[target],
        projects=[RemoteConfigProjectInventory(target=target, parameter_count=1)],
        keys=[RemoteConfigKeyInventory(key="feature_enabled")],
    )
    client.get_remote_config_inventory.side_effect = [
        FirebaseAuthRejectedError(
            "expired token",
            auth_source="keyring:ragnarok-ios_firebase_access_token",
        ),
        inventory,
    ]
    client.invalidate_access_token_source.return_value = True
    client.is_available.return_value = True
    ctx = _ctx(firebase=client)
    ctx.textual.ask_password.return_value = "fresh-manual-token"

    result = execute_firebase_remoteconfig_inventory_step(ctx)

    assert isinstance(result, Success)
    assert client.get_remote_config_inventory.call_count == 2
    client.get_access_token.assert_not_called()
    client.save_access_token.assert_called_once_with("fresh-manual-token")
    warning_messages = [
        call.args[0] for call in ctx.textual.warning_text.call_args_list
    ]
    assert "Saved Firebase auth was rejected." in warning_messages
    assert any("browser OAuth is not configured" in msg for msg in warning_messages)


def test_remoteconfig_inventory_prompts_oauth_client_id_after_rejected_token() -> None:
    client = _firebase_client()
    client.config = FirebasePluginConfig(projects=["yoigo-prod"])
    target = FirebaseProjectTarget(project_id="yoigo-prod")
    inventory = RemoteConfigInventory(
        targets=[target],
        projects=[RemoteConfigProjectInventory(target=target, parameter_count=1)],
        keys=[RemoteConfigKeyInventory(key="feature_enabled")],
    )
    client.get_remote_config_inventory.side_effect = [
        FirebaseAuthRejectedError(
            "expired token",
            auth_source="keyring:ragnarok-ios_firebase_access_token",
        ),
        inventory,
    ]
    client.invalidate_access_token_source.return_value = True
    client.get_access_token.return_value = "fresh-token"
    client.is_available.return_value = True
    client.save_oauth_client_id.side_effect = _save_oauth_client_id_mock(client)
    ctx = _ctx(firebase=client)
    ctx.textual.ask_text.return_value = "google-client-id"
    ctx.textual.ask_password.return_value = "google-client-secret"

    result = execute_firebase_remoteconfig_inventory_step(ctx)

    assert isinstance(result, Success)
    assert client.get_remote_config_inventory.call_count == 2
    client.save_oauth_client_id.assert_called_once_with(
        "google-client-id",
        client_secret="google-client-secret",
    )
    assert client.get_access_token.call_args.kwargs["interactive"] is True
    ctx.textual.ask_password.assert_called_once()
