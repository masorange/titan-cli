"""Google OAuth helpers for Firebase Remote Config access."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import secrets as secrets_module
from threading import Event, Thread
import time
from typing import Callable, Sequence
from urllib.parse import parse_qs, urlencode, urlparse
import webbrowser

import requests

from titan_cli.core.logging import get_logger
from titan_cli.core.oauth import (
    OAuthEventSink,
    OAuthRequest,
    OAuthTokenInvalidError,
    OAuthTokenSet,
)


AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

logger = get_logger(__name__)

CALLBACK_SUCCESS_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Titan Firebase Connection</title>
    <style>
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        padding: 24px;
        background: #f6f7fb;
        color: #182033;
        font-family: system-ui, sans-serif;
      }
      main {
        width: min(100%, 520px);
        background: #ffffff;
        border: 1px solid #d8deea;
        border-radius: 16px;
        padding: 28px;
        box-shadow: 0 18px 50px rgba(24, 32, 51, 0.10);
      }
      h1 { margin: 0 0 10px; font-size: 28px; }
      p { margin: 0; color: #5c667d; line-height: 1.55; }
      .status { margin-top: 20px; color: #15803d; font-weight: 700; }
    </style>
  </head>
  <body>
    <main>
      <h1>Firebase connection received</h1>
      <p>Titan has received the Google OAuth callback successfully.</p>
      <p class="status">You can close this tab and return to Titan.</p>
    </main>
  </body>
</html>
""".encode("utf-8")

CALLBACK_ERROR_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Titan Firebase Connection</title>
    <style>
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        padding: 24px;
        background: #f6f7fb;
        color: #182033;
        font-family: system-ui, sans-serif;
      }
      main {
        width: min(100%, 520px);
        background: #ffffff;
        border: 1px solid #d8deea;
        border-radius: 16px;
        padding: 28px;
        box-shadow: 0 18px 50px rgba(24, 32, 51, 0.10);
      }
      h1 { margin: 0 0 10px; font-size: 28px; }
      p { margin: 0; color: #5c667d; line-height: 1.55; }
      .status { margin-top: 20px; color: #b91c1c; font-weight: 700; }
    </style>
  </head>
  <body>
    <main>
      <h1>Firebase connection failed</h1>
      <p>Titan could not complete the Google OAuth callback.</p>
      <p class="status">Return to Titan to see the error details.</p>
    </main>
  </body>
</html>
""".encode("utf-8")


class GoogleOAuthError(Exception):
    """Raised when Google OAuth cannot complete."""


@dataclass(frozen=True)
class GoogleOAuthSession:
    """In-memory state for one Google OAuth PKCE flow."""

    state: str
    code_verifier: str


@dataclass(frozen=True)
class GoogleOAuthResult:
    """Token data returned by Google's OAuth token endpoint."""

    access_token: str
    refresh_token: str | None
    expires_in: int | None
    token_type: str
    granted_scopes: list[str] | None

    @property
    def expires_at(self) -> int | None:
        """Return absolute expiry time in epoch seconds."""
        if self.expires_in is None:
            return None
        return int(time.time()) + self.expires_in


class GoogleOAuthFlow:
    """Synchronous Google OAuth PKCE flow for installed applications."""

    def __init__(
        self,
        client_id: str,
        *,
        client_secret: str | None = None,
        redirect_port: int = 0,
        scopes: list[str] | None = None,
        timeout: int = 180,
        token_request_timeout: int = 30,
        browser_opener: Callable[[str], bool] | None = None,
        requests_module=requests,
    ) -> None:
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip() if client_secret else None
        self.redirect_port = redirect_port
        self.scopes = scopes or []
        self.timeout = timeout
        self.token_request_timeout = token_request_timeout
        self.browser_opener = browser_opener or webbrowser.open
        self.requests = requests_module
        self._bound_redirect_port: int | None = None

        if not self.client_id:
            raise GoogleOAuthError("Google OAuth client ID is required.")

    @property
    def redirect_uri(self) -> str:
        """Return the loopback redirect URI used for callback handling."""
        port = self._bound_redirect_port
        if port is None:
            port = self.redirect_port
        return f"http://127.0.0.1:{port}"

    @staticmethod
    def _build_code_challenge(code_verifier: str) -> str:
        """Build a PKCE S256 code challenge from a verifier."""
        digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

    def create_session(self) -> GoogleOAuthSession:
        """Create a new OAuth session with state and PKCE verifier."""
        return GoogleOAuthSession(
            state=secrets_module.token_urlsafe(24),
            code_verifier=secrets_module.token_urlsafe(48),
        )

    def build_authorize_url(self, session: GoogleOAuthSession) -> str:
        """Build the Google OAuth authorization URL."""
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(self.scopes),
                "state": session.state,
                "code_challenge": self._build_code_challenge(session.code_verifier),
                "code_challenge_method": "S256",
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
            }
        )
        logger.info(
            "google_oauth_authorize_url_built",
            redirect_uri=self.redirect_uri,
            scopes=self.scopes,
        )
        return f"{AUTHORIZE_URL}?{query}"

    def exchange_code(self, code: str, code_verifier: str) -> GoogleOAuthResult:
        """Exchange a Google authorization code for tokens."""
        data = {
            "client_id": self.client_id,
            "code": code,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret

        response = self.requests.post(
            TOKEN_URL,
            data=data,
            timeout=self.token_request_timeout,
        )
        payload = self._read_token_response(response, "exchange")
        return self._build_oauth_result(payload, require_refresh_token=True)

    def refresh_access_token(self, refresh_token: str) -> GoogleOAuthResult:
        """Refresh a Google OAuth access token."""
        normalized_refresh_token = refresh_token.strip() if refresh_token else ""
        if not normalized_refresh_token:
            raise GoogleOAuthError("Google OAuth refresh token is required.")

        data = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": normalized_refresh_token,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret

        response = self.requests.post(
            TOKEN_URL,
            data=data,
            timeout=self.token_request_timeout,
        )
        payload = self._read_token_response(response, "refresh")
        return self._build_oauth_result(payload, require_refresh_token=False)

    def run(self) -> GoogleOAuthResult:
        """Run the complete browser OAuth flow."""
        session = self.create_session()
        server, thread, callback_event, callback_data = self._start_callback_server(
            session.state
        )
        authorize_url = self.build_authorize_url(session)

        try:
            browser_started = self.browser_opener(authorize_url)
        except Exception:
            server.server_close()
            logger.error("google_oauth_browser_open_failed")
            raise

        if browser_started is False:
            server.server_close()
            logger.error("google_oauth_browser_open_failed")
            raise GoogleOAuthError("Failed to open a browser for Google OAuth.")

        code = self._wait_for_callback(
            session.state,
            server,
            thread,
            callback_event,
            callback_data,
        )
        return self.exchange_code(code, session.code_verifier)

    def _start_callback_server(
        self,
        expected_state: str,
    ) -> tuple[HTTPServer, Thread, Event, dict[str, str]]:
        """Bind and start the local OAuth callback listener."""
        callback_event = Event()
        callback_data: dict[str, str] = {}

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):  # type: ignore[override]
                parsed = urlparse(self.path)
                if parsed.path not in ("", "/", "/google/callback"):
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Not found")
                    return

                query = parse_qs(parsed.query)
                code = query.get("code", [""])[0]
                state = query.get("state", [""])[0]
                error = query.get("error", [""])[0]
                status_code, body, completed = _resolve_callback_response(
                    callback_data,
                    code=code,
                    state=state,
                    error=error,
                    expected_state=expected_state,
                )
                self._send_callback_response(status_code, body)
                if completed:
                    callback_event.set()

            def _send_callback_response(self, status_code: int, body: bytes) -> None:
                self.send_response(status_code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server = HTTPServer(("127.0.0.1", self.redirect_port), CallbackHandler)
        server.timeout = 0.5
        self._bound_redirect_port = int(server.server_address[1])

        def serve_until_callback() -> None:
            try:
                while not callback_event.is_set():
                    server.handle_request()
            finally:
                server.server_close()

        thread = Thread(target=serve_until_callback, daemon=True)
        thread.start()
        logger.info(
            "google_oauth_callback_listener_started",
            redirect_uri=self.redirect_uri,
        )
        return server, thread, callback_event, callback_data

    def _wait_for_callback(
        self,
        expected_state: str,
        server: HTTPServer,
        thread: Thread,
        callback_event: Event,
        callback_data: dict[str, str],
    ) -> str:
        """Wait for the local callback and return the authorization code."""
        callback_event.wait(self.timeout)
        server.server_close()
        thread.join(timeout=1)

        if not callback_event.is_set():
            raise GoogleOAuthError("Google OAuth callback timed out.")

        if callback_data.get("error"):
            raise GoogleOAuthError(
                f"Google OAuth authorization failed: {callback_data['error']}"
            )

        if callback_data.get("state") != expected_state:
            raise GoogleOAuthError("Google OAuth state mismatch.")

        code = callback_data.get("code")
        if not code:
            raise GoogleOAuthError(
                "Google OAuth callback did not include an authorization code."
            )
        return code

    def _read_token_response(self, response, operation: str) -> dict:
        try:
            payload = response.json()
        except ValueError as exc:
            raise GoogleOAuthError(
                f"Google OAuth {operation} response was not valid JSON."
            ) from exc

        if getattr(response, "status_code", 200) >= 400 or payload.get("error"):
            error = payload.get("error_description") or payload.get("error")
            error_name = payload.get("error")
            if operation == "refresh" and error_name == "invalid_grant":
                raise OAuthTokenInvalidError(
                    "Google OAuth refresh token is invalid or revoked."
                )
            error_text = error.lower() if isinstance(error, str) else ""
            if ("client_secret" in error_text or "client secret" in error_text) and (
                "missing" in error_text or "invalid" in error_text
            ):
                error = (
                    f"{error}. Enter the Client ID and Client Secret from the "
                    "same Google OAuth Desktop app client."
                )
            raise GoogleOAuthError(
                f"Google OAuth {operation} failed: {error or 'unknown_error'}"
            )

        return payload

    def _build_oauth_result(
        self,
        payload: dict,
        *,
        require_refresh_token: bool,
    ) -> GoogleOAuthResult:
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token.strip():
            raise GoogleOAuthError(
                "Google OAuth response did not include an access token."
            )

        refresh_token = payload.get("refresh_token")
        if require_refresh_token and not refresh_token:
            raise GoogleOAuthError(
                "Google OAuth response did not include a refresh token. "
                "Verify the OAuth client is configured for installed apps and "
                "that offline access consent was granted."
            )

        expires_in_raw = payload.get("expires_in")
        expires_in = int(expires_in_raw) if expires_in_raw is not None else None
        granted_scopes = None
        if "scope" in payload:
            granted_scopes = [
                scope.strip()
                for scope in str(payload.get("scope") or "").split()
                if scope.strip()
            ]

        return GoogleOAuthResult(
            access_token=access_token.strip(),
            refresh_token=(
                refresh_token.strip() if isinstance(refresh_token, str) else None
            ),
            expires_in=expires_in,
            token_type=str(payload.get("token_type") or "Bearer"),
            granted_scopes=granted_scopes,
        )


def _resolve_callback_response(
    callback_data: dict[str, str],
    *,
    code: str,
    state: str,
    error: str,
    expected_state: str,
) -> tuple[int, bytes, bool]:
    """Return the loopback callback response without closing on invalid state."""
    if state != expected_state:
        return 400, CALLBACK_ERROR_HTML, False

    if error:
        callback_data["code"] = code
        callback_data["state"] = state
        callback_data["error"] = error
        return 200, CALLBACK_ERROR_HTML, True

    if not code:
        return 400, CALLBACK_ERROR_HTML, False

    callback_data["code"] = code
    callback_data["state"] = state
    callback_data["error"] = error
    return 200, CALLBACK_SUCCESS_HTML, True


class GoogleOAuthProvider:
    """OAuthManager provider adapter for Google OAuth."""

    def __init__(self, flow: GoogleOAuthFlow) -> None:
        self.flow = flow

    async def refresh(
        self,
        request: OAuthRequest,
        token_set: OAuthTokenSet,
        sink: OAuthEventSink,
    ) -> OAuthTokenSet:
        """Refresh a Google OAuth token set."""
        if not token_set.refresh_token:
            raise GoogleOAuthError("Google OAuth refresh token is required.")

        result = await asyncio.to_thread(
            self.flow.refresh_access_token,
            token_set.refresh_token,
        )
        return self._to_token_set(
            result,
            request,
            fallback_refresh_token=token_set.refresh_token,
            fallback_scopes=token_set.scopes,
        )

    async def authorize(
        self,
        request: OAuthRequest,
        sink: OAuthEventSink,
    ) -> OAuthTokenSet:
        """Run an interactive Google OAuth login."""
        result = await asyncio.to_thread(self.flow.run)
        return self._to_token_set(result, request)

    def _to_token_set(
        self,
        result: GoogleOAuthResult,
        request: OAuthRequest,
        *,
        fallback_refresh_token: str | None = None,
        fallback_scopes: Sequence[str] | None = None,
    ) -> OAuthTokenSet:
        return OAuthTokenSet(
            access_token=result.access_token,
            refresh_token=result.refresh_token or fallback_refresh_token,
            expires_at=result.expires_at,
            token_type=result.token_type,
            scopes=(
                result.granted_scopes
                if result.granted_scopes is not None
                else (fallback_scopes or request.scopes)
            ),
            metadata={
                "provider": "google",
                "connection_id": request.connection_id,
            },
        )
