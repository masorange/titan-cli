"""Application Default Credentials: identity, quota project, and refresh."""

import pytest

from titan_plugin_firebase.clients.network import adc_auth
from titan_plugin_firebase.exceptions import FirebaseAuthUnavailableError


class FakeUserCredentials:
    """Stands in for google.oauth2.credentials.Credentials."""

    # The classifier reads the module name, which is how google-auth
    # distinguishes a user credential from a service account.
    __module__ = "google.oauth2.credentials"

    def __init__(self, quota_project_id=None, scopes=None):
        self.quota_project_id = quota_project_id
        self.scopes = scopes
        self.token = None
        self.refreshed = 0

    def with_quota_project(self, quota_project_id):
        return FakeUserCredentials(
            quota_project_id=quota_project_id,
            scopes=self.scopes,
        )

    def refresh(self, request):
        self.refreshed += 1
        self.token = "ya29.fake-token-value"


class FakeServiceAccountCredentials(FakeUserCredentials):
    """Stands in for google.oauth2.service_account.Credentials."""

    __module__ = "google.oauth2.service_account"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service_account_email = "ci@project.iam.gserviceaccount.com"


def test_describe_identity_names_the_credential_kind():
    identity = adc_auth.describe_identity(FakeUserCredentials())

    assert identity.credential_kind == "user"
    assert identity.is_user_credential is True
    # Titan does not resolve the signed-in email: an ADC token for
    # cloud-platform need not carry the userinfo scope, and Firebase records
    # the authoritative author on the published version.
    assert identity.account is None


def test_describe_identity_names_a_service_account():
    identity = adc_auth.describe_identity(FakeServiceAccountCredentials())

    assert identity.credential_kind == "service_account"
    assert identity.is_user_credential is False
    assert identity.account == "ci@project.iam.gserviceaccount.com"


def test_describe_identity_makes_no_network_call(monkeypatch):
    def _explode(*args, **kwargs):
        raise AssertionError("describe_identity must not perform HTTP")

    monkeypatch.setattr(adc_auth, "build_session", _explode)
    identity = adc_auth.describe_identity(
        FakeUserCredentials(quota_project_id="mm-ragnarok-dev")
    )
    assert identity.quota_project_id == "mm-ragnarok-dev"


def test_configured_quota_project_is_applied_to_the_credential(monkeypatch):
    original = FakeUserCredentials(quota_project_id="mm-firebase-yoigo")
    monkeypatch.setattr(
        "google.auth.default", lambda scopes=None: (original, "mm-firebase-yoigo")
    )

    resolved = adc_auth.resolve_credentials(
        ["scope"], quota_project_id="mm-ragnarok-dev"
    )

    # google.auth overwrites x-goog-user-project with the credential's quota
    # project on every request, so a header alone would be ignored whenever the
    # ADC session carries one of its own.
    assert resolved.quota_project_id == "mm-ragnarok-dev"
    assert original.quota_project_id == "mm-firebase-yoigo"


def test_credentials_are_returned_untouched_without_an_override(monkeypatch):
    original = FakeUserCredentials(quota_project_id="mm-firebase-yoigo")
    monkeypatch.setattr("google.auth.default", lambda scopes=None: (original, None))

    assert adc_auth.resolve_credentials(["scope"]) is original


def test_missing_adc_reports_the_login_command(monkeypatch):
    from google.auth.exceptions import DefaultCredentialsError

    def _no_adc(scopes=None):
        raise DefaultCredentialsError("nothing here")

    monkeypatch.setattr("google.auth.default", _no_adc)

    with pytest.raises(FirebaseAuthUnavailableError) as exc:
        adc_auth.resolve_credentials()
    assert "gcloud auth application-default login" in str(exc.value)


def test_refresh_registers_the_token_for_redaction(monkeypatch):
    registered = []
    monkeypatch.setattr("titan_cli.core.security.register_secret", registered.append)
    credentials = FakeUserCredentials()

    adc_auth.refresh_credentials(credentials)

    assert credentials.refreshed == 1
    # The token is never returned by this module, but it must be redactable in
    # case it reaches an error message or a command echo.
    assert registered == ["ya29.fake-token-value"]


def test_refresh_failure_tells_the_user_to_log_in_again(monkeypatch):
    from google.auth.exceptions import RefreshError

    class Expired(FakeUserCredentials):
        def refresh(self, request):
            raise RefreshError("token revoked")

    with pytest.raises(FirebaseAuthUnavailableError) as exc:
        adc_auth.refresh_credentials(Expired())
    assert "gcloud auth application-default login" in str(exc.value)


def test_service_account_env_var_detection(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    assert adc_auth.service_account_env_var_set() is False

    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/sa.json")
    assert adc_auth.service_account_env_var_set() is True
