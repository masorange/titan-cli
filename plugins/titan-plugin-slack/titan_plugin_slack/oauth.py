"""Slack OAuth backend helpers for the Slack configuration flow."""

from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Thread
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlparse
import secrets as secrets_module
import webbrowser

import requests


AUTHORIZE_URL = "https://slack.com/oauth/v2_user/authorize"
TOKEN_URL = "https://slack.com/api/oauth.v2.user.access"
DEFAULT_SCOPES = ["users:read", "channels:read", "channels:history"]


class SlackOAuthError(Exception):
    """Raised when the Slack OAuth flow fails."""


@dataclass
class SlackOAuthResult:
    """Successful OAuth exchange result."""

    access_token: str
    granted_scopes: list[str]
    team_id: str | None
    team_name: str | None
    authed_user_id: str | None


class SlackOAuthFlow:
    """Backend flow for Slack OAuth-based personal connections."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_port: int = 8765,
        scopes: list[str] | None = None,
        timeout: int = 180,
        browser_opener: Callable[[str], bool] | None = None,
        requests_module=requests,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_port = redirect_port
        self.scopes = scopes or list(DEFAULT_SCOPES)
        self.timeout = timeout
        self.browser_opener = browser_opener or webbrowser.open
        self.requests = requests_module

    @property
    def redirect_uri(self) -> str:
        """Return the localhost redirect URI used for callback handling."""
        return f"http://127.0.0.1:{self.redirect_port}/slack/callback"

    def build_authorize_url(self, state: str) -> str:
        """Build the Slack OAuth authorize URL."""
        query = urlencode(
            {
                "client_id": self.client_id,
                "scope": ",".join(self.scopes),
                "redirect_uri": self.redirect_uri,
                "state": state,
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    def exchange_code(self, code: str) -> SlackOAuthResult:
        """Exchange a Slack OAuth code for a user access token."""
        response = self.requests.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        if not payload.get("ok", False):
            raise SlackOAuthError(
                f"Slack OAuth token exchange failed: {payload.get('error', 'unknown_error')}"
            )

        access_token = payload.get("access_token") or payload.get("authed_user", {}).get("access_token")
        if not access_token:
            raise SlackOAuthError("Slack OAuth token exchange succeeded without an access token.")

        scope_string = payload.get("scope") or payload.get("authed_user", {}).get("scope") or ""
        granted_scopes = [scope.strip() for scope in scope_string.split(",") if scope.strip()]

        team = payload.get("team") or {}
        authed_user = payload.get("authed_user") or {}
        return SlackOAuthResult(
            access_token=access_token,
            granted_scopes=granted_scopes,
            team_id=team.get("id"),
            team_name=team.get("name"),
            authed_user_id=authed_user.get("id"),
        )

    def _wait_for_callback(self, expected_state: str) -> str:
        """Wait for the local OAuth callback and return the authorization code."""
        callback_event = Event()
        callback_data: dict[str, str] = {}

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):  # type: ignore[override]
                parsed = urlparse(self.path)
                if parsed.path != "/slack/callback":
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Not found")
                    return

                query = parse_qs(parsed.query)
                callback_data["code"] = query.get("code", [""])[0]
                callback_data["state"] = query.get("state", [""])[0]
                callback_data["error"] = query.get("error", [""])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h2>Slack connection received.</h2><p>You can return to Titan.</p></body></html>"
                )
                callback_event.set()

            def log_message(self, format, *args):  # noqa: A003
                return

        server = HTTPServer(("127.0.0.1", self.redirect_port), CallbackHandler)

        def serve_once() -> None:
            try:
                while not callback_event.is_set():
                    server.handle_request()
            finally:
                server.server_close()

        thread = Thread(target=serve_once, daemon=True)
        thread.start()
        callback_event.wait(self.timeout)
        server.server_close()
        thread.join(timeout=1)

        if not callback_event.is_set():
            raise SlackOAuthError("Slack OAuth callback timed out.")

        if callback_data.get("error"):
            raise SlackOAuthError(f"Slack OAuth authorization failed: {callback_data['error']}")

        if callback_data.get("state") != expected_state:
            raise SlackOAuthError("Slack OAuth state mismatch.")

        code = callback_data.get("code")
        if not code:
            raise SlackOAuthError("Slack OAuth callback did not include an authorization code.")

        return code

    def run(self) -> SlackOAuthResult:
        """Run the complete OAuth flow and return the resulting token data."""
        state = secrets_module.token_urlsafe(24)
        authorize_url = self.build_authorize_url(state)

        browser_started = self.browser_opener(authorize_url)
        if browser_started is False:
            raise SlackOAuthError("Failed to open a browser for Slack OAuth.")

        code = self._wait_for_callback(state)
        return self.exchange_code(code)
