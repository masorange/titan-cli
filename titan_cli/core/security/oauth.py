"""
OAuth 2.0 for desktop apps: authorization code + PKCE over a loopback redirect.

The whole token lifecycle stays inside the security boundary. A plugin
describes the provider (`OAuthProvider`) and its own app registration
(`OAuthApp`), calls `connect_oauth` once from its config screen, and later
builds an `OAuthCredentials` to obtain an authenticated `requests.Session` or
an SDK client. It never sees an access token, a refresh token or the token
endpoint's response: those go straight from the HTTP response into the
broker, and come back out only into a constructor (`create_client`) or a
request header (`session`).

What makes the flow safe on a shared machine:

- PKCE S256 with a fresh 64-byte verifier, and a 32-byte `state` compared in
  constant time. A callback with the wrong state is answered and ignored, so
  a local process cannot inject its own code.
- The callback server binds 127.0.0.1 only, answers one path, never reflects
  the query into its page, and stops after the first valid callback or the
  timeout.
- Response bodies are never logged or put in exception messages; only the
  provider's error code and non-secret fields are.
- Every token is registered for redaction as soon as it is parsed.
- An optional `verify` callback sees the non-secret grant (account, team…)
  before anything is stored, so the wrong account is rejected without its
  tokens ever reaching the keyring.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import secrets
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Mapping, Optional, TypeVar
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from requests.auth import AuthBase

from titan_cli.core.logging import get_logger

from .broker import SecretBroker, SecretLeakError
from .redaction import register_secret

logger = get_logger(__name__)

T = TypeVar("T")

REFRESH_MARGIN_SECONDS = 300
_HTTP_TIMEOUT_SECONDS = 30


class OAuthError(Exception):
    """The OAuth flow or a token refresh failed.

    `reauthorize` is True when the stored grant is no longer usable (revoked,
    expired refresh token, missing) and only connecting again fixes it.
    """

    def __init__(self, message: str, *, reauthorize: bool = False):
        super().__init__(message)
        self.reauthorize = reauthorize


@dataclass(frozen=True)
class OAuthProvider:
    """How a provider speaks OAuth. Declarative: no code touches the tokens.

    Attributes:
        name: Display name, used in the browser page and in logs.
        authorize_url: Authorization endpoint.
        token_url: Token endpoint (code exchange and refresh).
        scopes: Scopes requested on connect.
        scope_separator: How scopes are joined in the request and split in
            the response (" " in the RFC, "," for Slack).
        authorize_params: Extra authorization parameters
            (`prompt`, `access_type`…).
        callback_path: Path of the loopback redirect URI.
        success_flag: Response field that must be truthy (Slack's `ok`).
        token_container: Response object that holds the tokens when they are
            not at the root (Slack's `authed_user`). Fields are looked up at
            the root first, then here.
        metadata_fields: Non-secret response fields to keep, as
            `{name: "dotted.path"}`.
        id_token_claims: Claims of the OpenID `id_token` to keep as metadata
            (`email`, `sub`…). The token itself is never kept. Its signature is
            not checked: it comes straight from the token endpoint over TLS
            (OpenID Connect Core 3.1.3.7), so the claims say which account the
            user picked, which is what `verify` needs, not more.
        api_hosts: Hosts `OAuthCredentials.session()` may send the token to.
            Requests to any other host, or over plain http, are refused.
    """

    name: str
    authorize_url: str
    token_url: str
    scopes: tuple[str, ...]
    scope_separator: str = " "
    authorize_params: Mapping[str, str] = field(default_factory=dict)
    callback_path: str = "/oauth/callback"
    success_flag: Optional[str] = None
    token_container: Optional[str] = None
    metadata_fields: Mapping[str, str] = field(default_factory=dict)
    id_token_claims: tuple[str, ...] = ()
    api_hosts: tuple[str, ...] = ()


@dataclass(frozen=True)
class OAuthApp:
    """The user's registration of the app with the provider.

    Attributes:
        client_id: Public client id.
        client_secret_key: Broker key holding the client secret, for
            providers that want one even from public clients (Google). The
            secret is read only inside this module.
        redirect_port: Loopback port; 0 picks a free one (fine for Google,
            whose desktop clients accept any port). Providers that match the
            redirect URI exactly (Slack) need the registered port.
    """

    client_id: str
    client_secret_key: Optional[str] = None
    redirect_port: int = 0


@dataclass(frozen=True)
class OAuthGrant:
    """What a connection produced, without any secret."""

    scopes: tuple[str, ...]
    expires_at: Optional[int]
    has_refresh_token: bool
    metadata: Mapping[str, str]


@dataclass(frozen=True)
class _TokenSet:
    access_token: str = field(repr=False)
    refresh_token: Optional[str] = field(repr=False)
    expires_at: Optional[int]
    scopes: tuple[str, ...]
    metadata: Mapping[str, str]

    def grant(self) -> OAuthGrant:
        return OAuthGrant(
            scopes=self.scopes,
            expires_at=self.expires_at,
            has_refresh_token=bool(self.refresh_token),
            metadata=dict(self.metadata),
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "expires_at": self.expires_at,
                "scopes": list(self.scopes),
            }
        )

    @classmethod
    def from_json(cls, raw: Optional[str]) -> "_TokenSet":
        if not raw or not raw.strip():
            raise OAuthError("No OAuth grant is stored.", reauthorize=True)
        try:
            data = json.loads(raw)
            access_token = data["access_token"]
        except (ValueError, KeyError, TypeError):
            raise OAuthError("The stored OAuth grant is unreadable.", reauthorize=True) from None
        if not isinstance(access_token, str) or not access_token:
            raise OAuthError("The stored OAuth grant has no access token.", reauthorize=True)
        refresh_token = data.get("refresh_token") or None
        # The vault registered the JSON blob as one string; register the
        # tokens themselves so they are masked wherever they appear alone.
        register_secret(access_token)
        if isinstance(refresh_token, str):
            register_secret(refresh_token)
        expires_at = data.get("expires_at")
        return cls(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=int(expires_at) if isinstance(expires_at, (int, float)) else None,
            scopes=tuple(data.get("scopes") or ()),
            metadata={},
        )


# --- Response parsing ---------------------------------------------------------


def _dig(payload: Mapping[str, Any], path: str) -> Any:
    node: Any = payload
    for part in path.split("."):
        if not isinstance(node, Mapping):
            return None
        node = node.get(part)
    return node


def _lookup(provider: OAuthProvider, payload: Mapping[str, Any], name: str) -> Any:
    value = payload.get(name)
    if value is None and provider.token_container:
        value = _dig(payload, f"{provider.token_container}.{name}")
    return value


def _id_token_claims(id_token: Any, wanted: tuple[str, ...]) -> dict[str, str]:
    """Claims from an id_token received directly from the token endpoint over
    TLS (OpenID Connect Core 3.1.3.7 allows skipping signature checks then)."""
    if not wanted or not isinstance(id_token, str) or id_token.count(".") != 2:
        return {}
    body = id_token.split(".")[1]
    try:
        claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except ValueError:
        return {}
    if not isinstance(claims, Mapping):
        return {}
    return {name: str(claims[name]) for name in wanted if claims.get(name) is not None}


def _provider_error(payload: Any) -> str:
    """The provider's error code, never the body."""
    if isinstance(payload, Mapping):
        code = payload.get("error")
        if isinstance(code, Mapping):  # {"error": {"status": "...", ...}}
            code = code.get("status") or code.get("code")
        if code:
            return str(code)[:100]
    return "unknown_error"


def _parse_token_response(
    provider: OAuthProvider,
    response: requests.Response,
    previous_refresh_token: Optional[str] = None,
) -> _TokenSet:
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if not response.ok or not isinstance(payload, Mapping):
        code = _provider_error(payload)
        raise OAuthError(
            f"{provider.name} token endpoint answered {response.status_code} ({code}).",
            reauthorize=code == "invalid_grant",
        )
    if provider.success_flag and not payload.get(provider.success_flag):
        code = _provider_error(payload)
        raise OAuthError(
            f"{provider.name} token request failed ({code}).",
            reauthorize=code in {"invalid_grant", "invalid_refresh_token", "token_revoked"},
        )

    access_token = _lookup(provider, payload, "access_token")
    if not isinstance(access_token, str) or not access_token:
        raise OAuthError(f"{provider.name} token response has no access token.")
    register_secret(access_token)

    refresh_token = _lookup(provider, payload, "refresh_token")
    if isinstance(refresh_token, str) and refresh_token:
        register_secret(refresh_token)
    else:
        # Google and most providers only send a refresh token on the first
        # exchange; Slack rotates it on every refresh.
        refresh_token = previous_refresh_token

    expires_in = _lookup(provider, payload, "expires_in")
    expires_at = (
        int(time.time()) + int(expires_in) if isinstance(expires_in, (int, float)) else None
    )

    scope_value = _lookup(provider, payload, "scope")
    scopes = tuple(
        s.strip() for s in str(scope_value or "").split(provider.scope_separator) if s.strip()
    )

    metadata = {
        name: str(value)
        for name, path in provider.metadata_fields.items()
        if (value := _dig(payload, path)) is not None
    }
    metadata.update(_id_token_claims(payload.get("id_token"), provider.id_token_claims))

    return _TokenSet(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        scopes=scopes,
        metadata=metadata,
    )


def _token_request(
    provider: OAuthProvider,
    app: OAuthApp,
    broker: SecretBroker,
    data: dict[str, str],
    http: Any,
) -> requests.Response:
    data = {"client_id": app.client_id, **data}
    if app.client_secret_key:
        # The client secret crosses into the form data inside the broker call.
        data = broker.create_client(
            app.client_secret_key,
            lambda secret: {**data, "client_secret": secret} if secret else data,
            required=False,
        )
    try:
        return http.post(
            provider.token_url,
            data=data,
            headers={"Accept": "application/json"},
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise OAuthError(
            f"Could not reach the {provider.name} token endpoint ({type(exc).__name__})."
        ) from None


# --- Authorization (connect) --------------------------------------------------


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _page(provider_name: str, ok: bool) -> bytes:
    name = html.escape(provider_name)
    title = f"{name} connected" if ok else f"{name} connection failed"
    body = (
        "Titan received the authorization. You can close this tab and return to Titan."
        if ok
        else "Titan could not complete the authorization. Return to Titan to see why."
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Titan · {name}</title>"
        "<style>body{font-family:system-ui,sans-serif;display:grid;place-items:center;"
        "min-height:90vh;margin:0;background:#f5f7fb;color:#182033}"
        "main{max-width:480px;padding:28px;background:#fff;border:1px solid #d8deea;"
        "border-radius:16px}</style></head>"
        f"<body><main><h1>{title}</h1><p>{body}</p></main></body></html>"
    ).encode("utf-8")


class _Callback:
    """State shared between the loopback handler and the waiting caller."""

    def __init__(self, provider: OAuthProvider, state: str):
        self.provider = provider
        self.state = state
        self.done = threading.Event()
        self.code: Optional[str] = None
        self.error: Optional[str] = None


def _handler_for(callback: _Callback) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        # A local process that connects and sends nothing must not freeze
        # the wait loop (and with it the deadline and `cancel`).
        timeout = 2

        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != callback.provider.callback_path:
                self.send_response(404)
                self.end_headers()
                return
            query = parse_qs(parsed.query)
            state = query.get("state", [""])[0]
            if not hmac.compare_digest(state.encode(), callback.state.encode()):
                # Not our authorization: answer and keep waiting for the real one.
                logger.warning("oauth_callback_state_mismatch", provider=callback.provider.name)
                self._respond(400, ok=False)
                return
            error = query.get("error", [""])[0]
            code = query.get("code", [""])[0]
            if error or not code:
                callback.error = (error or "missing_code")[:100]
                self._respond(200, ok=False)
            else:
                callback.code = code
                self._respond(200, ok=True)
            callback.done.set()

        def _respond(self, status: int, ok: bool) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(_page(callback.provider.name, ok))

        def log_message(self, format, *args):  # noqa: A002 - silence stderr access log
            return

    return Handler


def connect_oauth(
    broker: SecretBroker,
    key: str,
    provider: OAuthProvider,
    app: OAuthApp,
    *,
    verify: Optional[Callable[[OAuthGrant], None]] = None,
    timeout: float = 180,
    cancel: Optional[threading.Event] = None,
    browser_opener: Optional[Callable[[str], bool]] = None,
    http: Any = requests,
) -> OAuthGrant:
    """Run the browser authorization and store the grant under `key`.

    Blocking: call it from a worker thread. Returns only non-secret data.

    Args:
        broker: The plugin's broker; the grant is stored in its namespace.
        key: Broker key for the grant (one key holds the whole token set).
        provider: The provider description.
        app: The user's app registration.
        verify: Called with the grant before it is stored. Raise
            `OAuthError` to reject it (wrong account, missing scope); nothing
            is stored then.
        timeout: Seconds to wait for the browser callback.
        cancel: Set it to abort the wait.
        browser_opener: Opens the authorization URL (default: webbrowser).
        http: Module or session with `post`, for tests.

    Raises:
        OAuthError: Authorization denied, timed out, cancelled, the code
            exchange failed, or `verify` rejected the grant.
    """
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    callback = _Callback(provider, state)

    try:
        server = HTTPServer(("127.0.0.1", app.redirect_port), _handler_for(callback))
    except OSError as exc:
        raise OAuthError(
            f"Could not listen on 127.0.0.1:{app.redirect_port} for the {provider.name} "
            f"callback ({exc.strerror or exc})."
        ) from None
    server.timeout = 0.25
    try:
        redirect_uri = f"http://127.0.0.1:{server.server_port}{provider.callback_path}"
        params = {
            "response_type": "code",
            "client_id": app.client_id,
            "redirect_uri": redirect_uri,
            "scope": provider.scope_separator.join(provider.scopes),
            "state": state,
            "code_challenge": _pkce_challenge(verifier),
            "code_challenge_method": "S256",
            **provider.authorize_params,
        }
        url = f"{provider.authorize_url}?{urlencode(params)}"
        logger.info("oauth_authorize_started", provider=provider.name, redirect_uri=redirect_uri)

        opener = browser_opener or webbrowser.open
        if opener(url) is False:
            raise OAuthError(f"Could not open a browser for {provider.name}.")

        deadline = time.monotonic() + timeout
        while not callback.done.is_set():
            if cancel is not None and cancel.is_set():
                raise OAuthError(f"{provider.name} authorization was cancelled.")
            if time.monotonic() > deadline:
                raise OAuthError(f"{provider.name} authorization timed out.")
            server.handle_request()
    finally:
        server.server_close()

    if callback.error:
        logger.warning("oauth_authorize_denied", provider=provider.name, error=callback.error)
        raise OAuthError(f"{provider.name} authorization failed ({callback.error}).")

    response = _token_request(
        provider,
        app,
        broker,
        {
            "grant_type": "authorization_code",
            "code": callback.code or "",
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
        http,
    )
    tokens = _parse_token_response(provider, response)
    grant = tokens.grant()

    if verify is not None:
        verify(grant)

    broker.store(key, tokens.to_json())
    logger.info(
        "oauth_connected",
        provider=provider.name,
        scopes=list(grant.scopes),
        has_refresh_token=grant.has_refresh_token,
        expires_at=grant.expires_at,
    )
    return grant


# --- Using a stored grant -----------------------------------------------------


class OAuthCredentials:
    """A stored grant, refreshed on demand. Hands out clients, never tokens.

    Refreshes are serialized within the process and re-read the store first,
    so a grant refreshed by another holder is reused. Honest limit: two
    processes refreshing a rotating grant (Slack) in the same instant can
    still spend the same refresh token; the loser gets `reauthorize=True`.
    """

    def __init__(
        self,
        broker: SecretBroker,
        key: str,
        provider: OAuthProvider,
        app: OAuthApp,
        *,
        http: Any = requests,
        refresh_margin: int = REFRESH_MARGIN_SECONDS,
    ):
        self._broker = broker
        self._key = key
        self._provider = provider
        self._app = app
        self._http = http
        self._margin = refresh_margin
        self._lock = threading.RLock()
        self._tokens: Optional[_TokenSet] = None

    def __repr__(self) -> str:
        return f"OAuthCredentials({self._provider.name}, {self._broker.namespace}:{self._key})"

    def __getstate__(self):
        raise TypeError("OAuthCredentials is not serializable")

    def exists(self) -> bool:
        return self._broker.exists(self._key)

    def disconnect(self) -> bool:
        """Delete the stored grant."""
        with self._lock:
            self._tokens = None
            return self._broker.delete(self._key)

    def _load(self) -> _TokenSet:
        if self._tokens is None:
            self._tokens = self._broker.create_client(
                self._key, _TokenSet.from_json, required=False
            )
        return self._tokens

    def _expiring(self, tokens: _TokenSet) -> bool:
        return tokens.expires_at is not None and tokens.expires_at <= time.time() + self._margin

    def _refresh_locked(self, stale: _TokenSet) -> _TokenSet:
        # Another holder of the same grant (the config screen, another Titan)
        # may have refreshed already; with rotating providers the refresh
        # token in memory would then be spent. Re-read the store first.
        self._tokens = None
        stored = self._load()
        if stored.access_token != stale.access_token and not self._expiring(stored):
            return stored
        stale = stored
        if not stale.refresh_token:
            raise OAuthError(
                f"{self._provider.name} grant has no refresh token; connect again.",
                reauthorize=True,
            )
        response = _token_request(
            self._provider,
            self._app,
            self._broker,
            {"grant_type": "refresh_token", "refresh_token": stale.refresh_token},
            self._http,
        )
        try:
            fresh = _parse_token_response(self._provider, response, stale.refresh_token)
        except OAuthError as exc:
            logger.warning(
                "oauth_refresh_failed", provider=self._provider.name, reauthorize=exc.reauthorize
            )
            raise
        # Persist before use: a rotating provider has already invalidated the
        # refresh token we just spent.
        self._broker.store(self._key, fresh.to_json())
        self._tokens = fresh
        logger.info("oauth_refreshed", provider=self._provider.name, expires_at=fresh.expires_at)
        return fresh

    def _current(self) -> _TokenSet:
        """The stored tokens, refreshed first when about to expire. A failed
        proactive refresh that does not require reconnecting falls back to the
        current token; the reactive path (401, `refresh`) handles the rest."""
        with self._lock:
            tokens = self._load()
            if not self._expiring(tokens) or not tokens.refresh_token:
                return tokens
            try:
                return self._refresh_locked(tokens)
            except OAuthError as exc:
                # Transient failure (network, 5xx): keep the current token and
                # let the provider's 401 drive the reactive refresh later. A
                # revoked grant is final.
                if exc.reauthorize:
                    raise
                return self._tokens or tokens

    def _refresh_if_unchanged(self, used: Optional[str]) -> _TokenSet:
        with self._lock:
            tokens = self._load()
            if used is not None and tokens.access_token != used:
                return tokens  # another caller already refreshed it
            return self._refresh_locked(tokens)

    def create_client(self, builder: Callable[[str], T]) -> T:
        """Pass a valid access token into `builder` and return what it built.

        Same contract and honest limit as `SecretBroker.create_client`: the
        built client keeps the token in its own memory; returning the token
        itself raises `SecretLeakError`.
        """
        token = self._current().access_token
        result = builder(token)
        _check_not_leaked(result, token, self._provider.name)
        return result

    def refresh(self, apply: Optional[Callable[[str], None]] = None) -> None:
        """Force a refresh (after the provider rejected the token) and hand
        the new access token to `apply`, e.g. to update an SDK client."""
        with self._lock:
            fresh = self._refresh_locked(self._load())
            if apply is not None:
                result = apply(fresh.access_token)
                _check_not_leaked(result, fresh.access_token, self._provider.name)

    def session(self) -> requests.Session:
        """A `requests.Session` that sends a valid bearer token on every
        request and, on a 401, refreshes once and retries."""
        session = requests.Session()
        session.auth = _BearerAuth(self)
        return session


def _check_not_leaked(result: Any, token: str, provider_name: str) -> None:
    if result is token or (isinstance(result, str) and token in result) or (
        isinstance(result, bytes) and token.encode() in result
    ):
        raise SecretLeakError(
            f"An OAuth builder for {provider_name} returned the access token "
            "instead of a constructed client."
        )


def _check_destination(provider: OAuthProvider, url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise OAuthError(f"Refusing to send the {provider.name} token over {parsed.scheme or 'no scheme'}.")
    if provider.api_hosts and parsed.hostname not in provider.api_hosts:
        raise OAuthError(f"Refusing to send the {provider.name} token to {parsed.hostname}.")


class _BearerAuth(AuthBase):
    def __init__(self, credentials: OAuthCredentials):
        self._credentials = credentials

    def __eq__(self, other):  # requests compares auth objects
        return isinstance(other, _BearerAuth) and other._credentials is self._credentials

    def __call__(self, request):
        _check_destination(self._credentials._provider, request.url)
        token = self._credentials._current().access_token
        request.headers["Authorization"] = f"Bearer {token}"
        request._titan_oauth_token = token  # which token this attempt used
        request.register_hook("response", self._retry_on_401)
        return request

    def _retry_on_401(self, response, **kwargs):
        request = response.request
        if response.status_code != 401 or getattr(request, "_titan_oauth_retried", False):
            return response
        try:
            fresh = self._credentials._refresh_if_unchanged(
                getattr(request, "_titan_oauth_token", None)
            )
        except OAuthError:
            return response  # the caller sees the original 401
        response.content  # release the connection  # noqa: B018
        response.close()
        retry = request.copy()
        retry.headers["Authorization"] = f"Bearer {fresh.access_token}"
        retry._titan_oauth_retried = True
        retried = response.connection.send(retry, **kwargs)
        retried.history.append(response)
        retried.request = retry
        return retried
