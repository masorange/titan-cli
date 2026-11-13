import base64
import hashlib
import json
import threading
import time
import urllib.error
import urllib.request
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
import requests
from requests.adapters import BaseAdapter

from titan_cli.core.security import (
    OAuthApp,
    OAuthCredentials,
    OAuthError,
    OAuthProvider,
    SecretBroker,
    SecretLeakError,
    connect_oauth,
    redaction,
)
from titan_cli.core.security._vault import SecretManager

GOOGLE_LIKE = OAuthProvider(
    name="Google",
    authorize_url="https://accounts.example.com/o/oauth2/v2/auth",
    token_url="https://oauth2.example.com/token",
    scopes=("openid", "email", "calendar"),
    authorize_params={"prompt": "select_account consent"},
    id_token_claims=("email",),
    api_hosts=("api.example.com",),
)

SLACK_LIKE = OAuthProvider(
    name="Slack",
    authorize_url="https://slack.example.com/oauth/v2_user/authorize",
    token_url="https://slack.example.com/api/oauth.v2.user.access",
    scopes=("users:read", "chat:write"),
    scope_separator=",",
    callback_path="/slack/callback",
    success_flag="ok",
    token_container="authed_user",
    metadata_fields={"team_id": "team.id", "user_id": "authed_user.id"},
)

KEY = "grant"


@pytest.fixture(autouse=True)
def clean_redaction_registry():
    redaction.clear_registry()
    yield
    redaction.clear_registry()


@pytest.fixture
def keyring_store():
    store: dict[tuple[str, str], str] = {}
    with patch("keyring.get_password", side_effect=lambda s, k: store.get((s, k))), \
         patch("keyring.set_password", side_effect=lambda s, k, v: store.__setitem__((s, k), v)), \
         patch("keyring.delete_password", side_effect=lambda s, k: store.pop((s, k), None)):
        yield store


@pytest.fixture
def broker(tmp_path, keyring_store, monkeypatch):
    monkeypatch.delenv("GRANT", raising=False)
    return SecretBroker(SecretManager(project_path=tmp_path), "titan.plugins.test")


def _response(status: int, payload) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(payload).encode()
    response.headers["Content-Type"] = "application/json"
    return response


def _id_token(claims: dict) -> str:
    def part(data):
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    return f"{part({'alg': 'RS256'})}.{part(claims)}.signature"


class FakeHttp:
    def __init__(self, *responses: requests.Response):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append({"url": url, "data": dict(data)})
        return self.responses.pop(0)


def _browser(query_for_state=None, delay=0.05):
    """A browser that follows the authorization URL to the loopback redirect."""
    seen = {}

    def opener(url: str) -> bool:
        params = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        seen.update(params)
        query = (query_for_state or (lambda state: {"code": "the-code", "state": state}))(
            params["state"]
        )

        def hit():
            time.sleep(delay)
            try:
                urllib.request.urlopen(f"{params['redirect_uri']}?{urlencode(query)}", timeout=5)
            except urllib.error.HTTPError:
                pass

        threading.Thread(target=hit, daemon=True).start()
        return True

    return opener, seen


def _stored(broker) -> dict:
    return broker.create_client(KEY, lambda raw: json.loads(raw))


# --- connect ------------------------------------------------------------------


def test_connect_uses_pkce_and_stores_the_grant(broker):
    http = FakeHttp(
        _response(200, {
            "access_token": "ya29.access",
            "refresh_token": "1//refresh",
            "expires_in": 3599,
            "scope": "openid email calendar",
            "id_token": _id_token({"email": "me@gmail.com", "sub": "42"}),
        })
    )
    opener, seen = _browser()

    grant = connect_oauth(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), browser_opener=opener, http=http)

    assert seen["code_challenge_method"] == "S256"
    assert seen["prompt"] == "select_account consent"
    assert seen["redirect_uri"].startswith("http://127.0.0.1:")
    exchange = http.calls[0]["data"]
    assert exchange["grant_type"] == "authorization_code"
    assert exchange["code"] == "the-code"
    assert exchange["redirect_uri"] == seen["redirect_uri"]
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(exchange["code_verifier"].encode()).digest()
    ).decode().rstrip("=")
    assert seen["code_challenge"] == expected

    assert grant.metadata == {"email": "me@gmail.com"}
    assert grant.scopes == ("openid", "email", "calendar")
    assert grant.has_refresh_token
    assert "ya29.access" not in repr(grant)
    stored = _stored(broker)
    assert stored["access_token"] == "ya29.access"
    assert stored["refresh_token"] == "1//refresh"
    assert "id_token" not in stored
    assert "ya29.access" not in redaction.redact("token ya29.access")
    assert "1//refresh" not in redaction.redact("token 1//refresh")


def test_connect_sends_the_client_secret_from_the_broker(broker):
    broker.store("client_secret", "GOCSPX-secret")
    http = FakeHttp(_response(200, {"access_token": "a", "refresh_token": "r"}))
    opener, _ = _browser()

    connect_oauth(
        broker, KEY, GOOGLE_LIKE, OAuthApp("cid", client_secret_key="client_secret"),
        browser_opener=opener, http=http,
    )

    assert http.calls[0]["data"]["client_secret"] == "GOCSPX-secret"


def test_connect_ignores_a_callback_with_the_wrong_state(broker):
    http = FakeHttp(_response(200, {"access_token": "a"}))

    connect_oauth(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), browser_opener=_forged_then_real(), http=http)

    assert http.calls[0]["data"]["code"] == "the-code"


def _forged_then_real():
    def opener(url: str) -> bool:
        params = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}

        def hit():
            time.sleep(0.05)
            try:
                urllib.request.urlopen(f"{params['redirect_uri']}?code=evil&state=forged", timeout=5)
            except urllib.error.HTTPError as exc:
                assert exc.code == 400
            urllib.request.urlopen(
                f"{params['redirect_uri']}?{urlencode({'code': 'the-code', 'state': params['state']})}",
                timeout=5,
            )

        threading.Thread(target=hit, daemon=True).start()
        return True

    return opener


def test_connect_reports_a_denied_authorization(broker):
    opener, _ = _browser(lambda state: {"error": "access_denied", "state": state})

    with pytest.raises(OAuthError, match="access_denied"):
        connect_oauth(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), browser_opener=opener, http=FakeHttp())

    assert not broker.exists(KEY)


def test_connect_times_out(broker):
    with pytest.raises(OAuthError, match="timed out"):
        connect_oauth(
            broker, KEY, GOOGLE_LIKE, OAuthApp("cid"),
            browser_opener=lambda url: True, http=FakeHttp(), timeout=0.3,
        )


def test_connect_can_be_cancelled(broker):
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(OAuthError, match="cancelled"):
        connect_oauth(
            broker, KEY, GOOGLE_LIKE, OAuthApp("cid"),
            browser_opener=lambda url: True, http=FakeHttp(), cancel=cancel,
        )


def test_verify_rejects_before_anything_is_stored(broker):
    http = FakeHttp(
        _response(200, {"access_token": "a", "id_token": _id_token({"email": "work@corp.com"})})
    )
    opener, _ = _browser()

    def only_personal(grant):
        if grant.metadata.get("email") != "me@gmail.com":
            raise OAuthError("wrong account")

    with pytest.raises(OAuthError, match="wrong account"):
        connect_oauth(
            broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), verify=only_personal,
            browser_opener=opener, http=http,
        )

    assert not broker.exists(KEY)


def test_token_endpoint_errors_never_carry_the_body(broker):
    http = FakeHttp(_response(400, {"error": "invalid_client", "leak": "ya29.should-not-show"}))
    opener, _ = _browser()

    with pytest.raises(OAuthError) as excinfo:
        connect_oauth(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), browser_opener=opener, http=http)

    assert "invalid_client" in str(excinfo.value)
    assert "should-not-show" not in str(excinfo.value)


def test_slack_style_response_is_read_from_the_container(broker):
    http = FakeHttp(
        _response(200, {
            "ok": True,
            "team": {"id": "T1"},
            "authed_user": {
                "id": "U1",
                "access_token": "xoxe.xoxp-a",
                "refresh_token": "xoxe-r",
                "expires_in": 43200,
                "scope": "users:read,chat:write",
            },
        })
    )
    opener, seen = _browser()

    grant = connect_oauth(
        broker, KEY, SLACK_LIKE, OAuthApp("cid", redirect_port=0), browser_opener=opener, http=http
    )

    assert seen["scope"] == "users:read,chat:write"
    assert urlparse(seen["redirect_uri"]).path == "/slack/callback"
    assert grant.metadata == {"team_id": "T1", "user_id": "U1"}
    assert grant.scopes == ("users:read", "chat:write")
    assert _stored(broker)["access_token"] == "xoxe.xoxp-a"


def test_slack_style_failure_flag_is_an_error(broker):
    http = FakeHttp(_response(200, {"ok": False, "error": "invalid_code"}))
    opener, _ = _browser()

    with pytest.raises(OAuthError, match="invalid_code"):
        connect_oauth(broker, KEY, SLACK_LIKE, OAuthApp("cid"), browser_opener=opener, http=http)


# --- credentials --------------------------------------------------------------


def _seed(broker, *, access="old", refresh="r1", expires_at=None):
    broker.store(KEY, json.dumps({
        "access_token": access,
        "refresh_token": refresh,
        "expires_at": expires_at if expires_at is not None else int(time.time()) + 3600,
        "scopes": [],
    }))


def test_create_client_passes_a_valid_token(broker):
    _seed(broker)
    creds = OAuthCredentials(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), http=FakeHttp())

    assert creds.create_client(lambda token: {"built_with": token}) == {"built_with": "old"}


def test_create_client_refuses_to_return_the_token(broker):
    _seed(broker)
    creds = OAuthCredentials(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), http=FakeHttp())

    with pytest.raises(SecretLeakError):
        creds.create_client(lambda token: token)
    with pytest.raises(SecretLeakError):
        creds.create_client(lambda token: f"Bearer {token}")


def test_expiring_token_is_refreshed_and_the_refresh_token_kept(broker):
    _seed(broker, expires_at=int(time.time()) + 10)
    http = FakeHttp(_response(200, {"access_token": "new", "expires_in": 3600}))
    creds = OAuthCredentials(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), http=http)

    assert creds.create_client(lambda token: [token]) == ["new"]

    assert http.calls[0]["data"] == {"client_id": "cid", "grant_type": "refresh_token", "refresh_token": "r1"}
    stored = _stored(broker)
    assert stored["access_token"] == "new"
    assert stored["refresh_token"] == "r1"


def test_rotated_refresh_token_is_persisted(broker):
    _seed(broker, expires_at=int(time.time()) + 10)
    http = FakeHttp(_response(200, {"ok": True, "authed_user": {"access_token": "new", "refresh_token": "r2"}}))
    creds = OAuthCredentials(broker, KEY, SLACK_LIKE, OAuthApp("cid"), http=http)

    creds.create_client(lambda token: [token])

    assert _stored(broker)["refresh_token"] == "r2"


def test_failed_transient_refresh_falls_back_even_to_an_expired_token(broker):
    _seed(broker, expires_at=int(time.time()) - 10)
    http = FakeHttp(_response(503, {"error": "backend_error"}))
    creds = OAuthCredentials(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), http=http)

    assert creds.create_client(lambda token: [token]) == ["old"]


def test_loaded_tokens_are_registered_for_redaction(broker):
    _seed(broker, access="ya29.loaded-access", refresh="1//loaded-refresh")
    redaction.clear_registry()
    creds = OAuthCredentials(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), http=FakeHttp())

    creds.create_client(lambda token: [token])

    assert "ya29.loaded-access" not in redaction.redact("x ya29.loaded-access")
    assert "1//loaded-refresh" not in redaction.redact("x 1//loaded-refresh")
    assert "loaded" not in repr(creds._tokens)


def test_session_refuses_other_hosts_and_plain_http(broker):
    _seed(broker)
    session = OAuthCredentials(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), http=FakeHttp()).session()
    session.mount("https://", ScriptedAdapter())
    session.mount("http://", ScriptedAdapter())

    with pytest.raises(OAuthError, match="evil.example.com"):
        session.get("https://evil.example.com/steal")
    with pytest.raises(OAuthError, match="http"):
        session.get("http://api.example.com/calendars")


def test_an_idle_connection_does_not_block_the_callback(broker):
    import socket

    http = FakeHttp(_response(200, {"access_token": "a"}))
    idle = []

    def opener(url):
        params = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        port = urlparse(params["redirect_uri"]).port
        idle.append(socket.create_connection(("127.0.0.1", port)))  # sends nothing
        return _browser(delay=0.1)[0](url)

    started = time.monotonic()
    connect_oauth(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), browser_opener=opener, http=http, timeout=10)

    assert time.monotonic() - started < 5
    idle[0].close()


def test_failed_proactive_refresh_falls_back_to_a_still_valid_token(broker):
    _seed(broker, expires_at=int(time.time()) + 10)
    http = FakeHttp(_response(500, {"error": "backend_error"}))
    creds = OAuthCredentials(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), http=http)

    assert creds.create_client(lambda token: [token]) == ["old"]


def test_revoked_grant_asks_to_reconnect(broker):
    _seed(broker, expires_at=int(time.time()) - 10)
    http = FakeHttp(_response(400, {"error": "invalid_grant"}))
    creds = OAuthCredentials(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), http=http)

    with pytest.raises(OAuthError) as excinfo:
        creds.create_client(lambda token: [token])
    assert excinfo.value.reauthorize


def test_missing_grant_asks_to_reconnect(broker):
    creds = OAuthCredentials(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), http=FakeHttp())

    with pytest.raises(OAuthError) as excinfo:
        creds.create_client(lambda token: [token])
    assert excinfo.value.reauthorize


def test_refresh_hands_the_new_token_to_apply(broker):
    _seed(broker)
    http = FakeHttp(_response(200, {"access_token": "new"}))
    creds = OAuthCredentials(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), http=http)
    applied = []

    creds.refresh(applied.append)

    assert applied == ["new"]


def test_refresh_uses_a_grant_refreshed_elsewhere(broker):
    _seed(broker, expires_at=int(time.time()) + 10)
    http = FakeHttp()
    creds = OAuthCredentials(broker, KEY, SLACK_LIKE, OAuthApp("cid"), http=http)
    creds._load()  # this holder cached the old grant
    _seed(broker, access="refreshed-elsewhere", refresh="r2")

    assert creds.create_client(lambda token: [token]) == ["refreshed-elsewhere"]
    assert http.calls == []


def test_disconnect_deletes_the_grant(broker):
    _seed(broker)
    creds = OAuthCredentials(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), http=FakeHttp())

    creds.disconnect()

    assert not creds.exists()


def test_credentials_are_not_serializable(broker):
    import pickle

    creds = OAuthCredentials(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), http=FakeHttp())
    with pytest.raises(TypeError):
        pickle.dumps(creds)


class ScriptedAdapter(BaseAdapter):
    """Answers 401 to `old` and 200 to anything else, recording headers."""

    def __init__(self):
        super().__init__()
        self.seen: list[str] = []

    def send(self, request, **kwargs):
        auth = request.headers.get("Authorization", "")
        self.seen.append(auth)
        response = _response(401 if auth == "Bearer old" else 200, {})
        response.request = request
        response.connection = self
        response.url = request.url
        return response

    def close(self):
        pass


def test_session_refreshes_once_on_401_and_retries(broker):
    _seed(broker)
    http = FakeHttp(_response(200, {"access_token": "new"}))
    creds = OAuthCredentials(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), http=http)
    session = creds.session()
    adapter = ScriptedAdapter()
    session.mount("https://", adapter)

    response = session.get("https://api.example.com/calendars")

    assert response.status_code == 200
    assert adapter.seen == ["Bearer old", "Bearer new"]
    assert len(http.calls) == 1
    assert "Authorization" not in session.headers


def test_session_returns_the_401_when_refresh_fails(broker):
    _seed(broker)
    http = FakeHttp(_response(400, {"error": "invalid_grant"}))
    creds = OAuthCredentials(broker, KEY, GOOGLE_LIKE, OAuthApp("cid"), http=http)
    session = creds.session()
    session.mount("https://", ScriptedAdapter())

    assert session.get("https://api.example.com/calendars").status_code == 401
