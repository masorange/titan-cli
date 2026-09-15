"""Service layer: API failures become ClientResults, never exceptions."""

from titan_cli.core.result import ClientError, ClientSuccess

from titan_plugin_firebase.clients.services.remoteconfig_service import (
    RemoteConfigService,
)
from titan_plugin_firebase.exceptions import FirebaseAuthUnavailableError


def test_get_template_returns_ui_model(make_network, make_response, template_payload):
    service = RemoteConfigService(
        make_network([make_response(200, template_payload, {"ETag": "etag-1"})])
    )
    result = service.get_template("mm-firebase-yoigo")

    assert isinstance(result, ClientSuccess)
    assert result.data.project_id == "mm-firebase-yoigo"
    assert result.data.etag == "etag-1"
    assert result.data.parameter_count == 3


def test_etag_conflict_is_a_warning_level_error(make_network, make_response):
    service = RemoteConfigService(
        make_network([make_response(409, {"error": {"message": "conflict"}})])
    )
    result = service.get_template("mm-firebase-yoigo")

    assert isinstance(result, ClientError)
    assert result.error_code == "ETAG_CONFLICT"
    # A stale ETag is recoverable control flow, not a failure to alarm about.
    assert result.log_level == "warning"


def test_permission_denied_is_error_level(make_network, make_response):
    service = RemoteConfigService(
        make_network([make_response(403, {"error": {"message": "nope"}})])
    )
    result = service.get_template("mm-firebase-yoigo")

    assert isinstance(result, ClientError)
    assert result.error_code == "PERMISSION_DENIED"
    assert result.log_level == "error"


def test_missing_adc_reports_the_login_command(make_network, monkeypatch):
    network = make_network([])

    def _no_adc(self):
        raise FirebaseAuthUnavailableError("sin credenciales")

    monkeypatch.setattr(type(network), "adc_session", property(_no_adc))
    result = RemoteConfigService(network).get_template("mm-firebase-yoigo")

    assert isinstance(result, ClientError)
    assert result.error_code == "ADC_UNAVAILABLE"
    assert "application-default login" in result.details["login_command"]


def test_check_auth_reports_the_identity(make_network):
    result = RemoteConfigService(make_network([])).check_auth()

    assert isinstance(result, ClientSuccess)
    assert result.data.account == "alex@example.com"
    assert result.data.is_user_credential is True


def test_raw_template_returns_payload_for_writes(
    make_network, make_response, template_payload
):
    service = RemoteConfigService(
        make_network([make_response(200, template_payload, {"ETag": "etag-1"})])
    )
    payload, etag, error = service.raw_template("mm-firebase-yoigo")

    assert error is None
    assert etag == "etag-1"
    # The raw payload is what a publish needs: the UI model is lossy.
    assert payload["parameters"]["feature_enabled"]["valueType"] == "BOOLEAN"
    assert payload["parameterGroups"] == template_payload["parameterGroups"]
