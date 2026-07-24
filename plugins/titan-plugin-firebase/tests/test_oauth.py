import asyncio
from urllib.parse import parse_qs, urlparse

import pytest

from titan_cli.core.oauth import OAuthRequest, OAuthTokenInvalidError, OAuthTokenSet
from titan_plugin_firebase.oauth import (
    AUTHORIZE_URL,
    TOKEN_URL,
    GoogleOAuthError,
    GoogleOAuthFlow,
    GoogleOAuthProvider,
    GoogleOAuthSession,
    _resolve_callback_response,
)


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload


class FakeRequests:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.post_calls = []

    def post(self, url: str, data: dict, timeout: int):
        self.post_calls.append((url, data, timeout))
        return self.response


def test_google_oauth_authorize_url_requests_offline_access() -> None:
    flow = GoogleOAuthFlow(
        client_id="client-id",
        redirect_port=8766,
        scopes=["scope-a", "scope-b"],
    )
    session = GoogleOAuthSession(state="state", code_verifier="verifier")

    authorize_url = flow.build_authorize_url(session)

    parsed = urlparse(authorize_url)
    query = parse_qs(parsed.query)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == AUTHORIZE_URL
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == ["http://127.0.0.1:8766"]
    assert query["response_type"] == ["code"]
    assert query["scope"] == ["scope-a scope-b"]
    assert query["access_type"] == ["offline"]
    assert query["prompt"] == ["consent"]
    assert query["code_challenge_method"] == ["S256"]


def test_google_oauth_callback_ignores_requests_without_expected_state() -> None:
    callback_data = {}

    status, _body, completed = _resolve_callback_response(
        callback_data,
        code="",
        state="",
        error="",
        expected_state="expected-state",
    )
    assert status == 400
    assert completed is False
    assert callback_data == {}

    status, _body, completed = _resolve_callback_response(
        callback_data,
        code="wrong-code",
        state="wrong-state",
        error="",
        expected_state="expected-state",
    )
    assert status == 400
    assert completed is False
    assert callback_data == {}

    status, _body, completed = _resolve_callback_response(
        callback_data,
        code="",
        state="expected-state",
        error="",
        expected_state="expected-state",
    )
    assert status == 400
    assert completed is False
    assert callback_data == {}

    status, _body, completed = _resolve_callback_response(
        callback_data,
        code="good-code",
        state="expected-state",
        error="",
        expected_state="expected-state",
    )
    assert status == 200
    assert completed is True
    assert callback_data == {
        "code": "good-code",
        "state": "expected-state",
        "error": "",
    }


def test_google_oauth_callback_accepts_provider_error_with_expected_state() -> None:
    callback_data = {}

    status, _body, completed = _resolve_callback_response(
        callback_data,
        code="",
        state="expected-state",
        error="access_denied",
        expected_state="expected-state",
    )

    assert status == 200
    assert completed is True
    assert callback_data == {
        "code": "",
        "state": "expected-state",
        "error": "access_denied",
    }


def test_google_oauth_exchange_code_requires_refresh_token() -> None:
    requests_module = FakeRequests(
        FakeResponse(
            {
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "scope-a scope-b",
            }
        )
    )
    flow = GoogleOAuthFlow(
        client_id="client-id",
        redirect_port=8766,
        scopes=["scope-a"],
        requests_module=requests_module,
    )

    result = flow.exchange_code("code", "verifier")

    assert result.access_token == "access"
    assert result.refresh_token == "refresh"
    assert result.expires_in == 3600
    assert result.granted_scopes == ["scope-a", "scope-b"]
    assert requests_module.post_calls == [
        (
            TOKEN_URL,
            {
                "client_id": "client-id",
                "code": "code",
                "code_verifier": "verifier",
                "grant_type": "authorization_code",
                "redirect_uri": "http://127.0.0.1:8766",
            },
            30,
        )
    ]


def test_google_oauth_exchange_code_sends_client_secret_when_configured() -> None:
    requests_module = FakeRequests(
        FakeResponse(
            {
                "access_token": "access",
                "refresh_token": "refresh",
            }
        )
    )
    flow = GoogleOAuthFlow(
        client_id="client-id",
        client_secret="client-secret",
        redirect_port=8766,
        requests_module=requests_module,
    )

    flow.exchange_code("code", "verifier")

    assert requests_module.post_calls[0][1]["client_secret"] == "client-secret"


def test_google_oauth_exchange_code_errors_without_refresh_token() -> None:
    flow = GoogleOAuthFlow(
        client_id="client-id",
        redirect_port=8766,
        requests_module=FakeRequests(FakeResponse({"access_token": "access"})),
    )

    with pytest.raises(GoogleOAuthError, match="refresh token"):
        flow.exchange_code("code", "verifier")


def test_google_oauth_exchange_code_explains_web_client_secret_error() -> None:
    flow = GoogleOAuthFlow(
        client_id="client-id",
        redirect_port=8766,
        requests_module=FakeRequests(
            FakeResponse(
                {
                    "error": "invalid_request",
                    "error_description": "client_secret is missing.",
                },
                status_code=400,
            )
        ),
    )

    with pytest.raises(GoogleOAuthError) as raised:
        flow.exchange_code("code", "verifier")

    assert "Desktop app" in str(raised.value)


def test_google_oauth_refresh_access_token_keeps_existing_refresh_token() -> None:
    requests_module = FakeRequests(
        FakeResponse(
            {
                "access_token": "fresh",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        )
    )
    flow = GoogleOAuthFlow(
        client_id="client-id",
        redirect_port=8766,
        requests_module=requests_module,
    )

    result = flow.refresh_access_token("refresh")

    assert result.access_token == "fresh"
    assert result.refresh_token is None
    assert result.granted_scopes is None
    assert requests_module.post_calls[0][1] == {
        "client_id": "client-id",
        "grant_type": "refresh_token",
        "refresh_token": "refresh",
    }


def test_google_oauth_refresh_sends_client_secret_when_configured() -> None:
    requests_module = FakeRequests(
        FakeResponse(
            {
                "access_token": "fresh",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        )
    )
    flow = GoogleOAuthFlow(
        client_id="client-id",
        client_secret="client-secret",
        requests_module=requests_module,
    )

    flow.refresh_access_token("refresh")

    assert requests_module.post_calls[0][1]["client_secret"] == "client-secret"


def test_google_oauth_refresh_access_token_marks_invalid_grant() -> None:
    flow = GoogleOAuthFlow(
        client_id="client-id",
        requests_module=FakeRequests(
            FakeResponse(
                {
                    "error": "invalid_grant",
                    "error_description": "Token has been expired or revoked.",
                },
                status_code=400,
            )
        ),
    )

    with pytest.raises(OAuthTokenInvalidError, match="invalid or revoked"):
        flow.refresh_access_token("refresh")


def test_google_oauth_provider_refresh_preserves_omitted_scope() -> None:
    requests_module = FakeRequests(
        FakeResponse(
            {
                "access_token": "fresh",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        )
    )
    flow = GoogleOAuthFlow(
        client_id="client-id",
        scopes=["new-scope"],
        requests_module=requests_module,
    )
    provider = GoogleOAuthProvider(flow)
    request = OAuthRequest(
        provider="google",
        connection_id="firebase:demo",
        scopes=["new-scope"],
    )
    token_set = OAuthTokenSet(
        access_token="old",
        refresh_token="refresh",
        scopes=["old-scope"],
    )

    refreshed = asyncio.run(provider.refresh(request, token_set, sink=None))

    assert refreshed.access_token == "fresh"
    assert refreshed.refresh_token == "refresh"
    assert refreshed.scopes == ("old-scope",)


def test_google_oauth_provider_refresh_uses_returned_scopes_when_present() -> None:
    requests_module = FakeRequests(
        FakeResponse(
            {
                "access_token": "fresh",
                "scope": "returned-scope",
            }
        )
    )
    provider = GoogleOAuthProvider(
        GoogleOAuthFlow(
            client_id="client-id",
            scopes=["new-scope"],
            requests_module=requests_module,
        )
    )
    request = OAuthRequest(
        provider="google",
        connection_id="firebase:demo",
        scopes=["new-scope"],
    )
    token_set = OAuthTokenSet(
        access_token="old",
        refresh_token="refresh",
        scopes=["old-scope"],
    )

    refreshed = asyncio.run(provider.refresh(request, token_set, sink=None))

    assert refreshed.scopes == ("returned-scope",)
